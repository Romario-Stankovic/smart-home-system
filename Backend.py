import time
import requests
import imaplib
import smtplib
from serial import Serial
from threading import Thread
import numpy as np
import matplotlib.pyplot as plt
import datetime
from email.mime.multipart import MIMEMultipart
from email.mime.image import MIMEImage
from email.mime.text import MIMEText
import io
from apscheduler.schedulers.background import BackgroundScheduler
from dotenv import load_dotenv
import os

load_dotenv()

# Arduino variables
PORT = os.getenv("ARDUINO_PORT")
BAUD_RATE = os.getenv("ARDUINO_BAUD_RATE")

# ThingSpeak variables
CHANNEL_ID = os.getenv("THINGSPEAK_CHANNEL_ID")
API_WRITE_KEY = os.getenv("THINGSPEAK_API_WRITE_KEY")
API_READ_KEY = os.getenv("THINGSPEAK_API_READ_KEY")

BASE_URL = "https://api.thingspeak.com"
WRITE_URL = f"{BASE_URL}/update?api_key={API_WRITE_KEY}"
READ_CHANNEL_URL = f"{BASE_URL}/channels/{CHANNEL_ID}/feeds.json?api_key={API_READ_KEY}"

# Email variables
EMAIL=os.getenv("EMAIL")
EMAIL_PW=os.getenv("EMAIL_PASSWORD")

# System variables
THINGSPEAK_SEND_INTERVAL = os.getenv("THINGSPEAK_SEND_INTERVAL")
EMAIL_READ_INTERVAL = os.getenv("EMAIL_READ_INTERVAL")

# data object that stores all data sent to ThingSpeak
data = {
    "temperature": 0,
    "illumination": 0,
    "detections": 0,
    "homeSecureModeDuration": 0,
    "lightAutoModeDuration": 0
}

# Dates when home secure mode and light auto mode were turned on
lastHomeSecureTimestamp = None
lastLightAutoModeTimestamp = datetime.datetime.now()

# Read data from the serial port
def readSerial(serial : Serial):

    # Define variables as global (python is a bit stupid :3)
    global lastHomeSecureTimestamp
    global lastLightAutoModeTimestamp

    # Read data from serial
    while True:

        # Check if we have data
        if serial.in_waiting > 0:
            
            # Read the message
            message = serial.readline().decode('ascii')

            # Print data to serial for debugging
            print("Serial: ", message, end="")

            if(message.startswith("temperature:")):
                # Store current measured temperature
                data['temperature'] = int(message[12:])
            elif(message.startswith("illumination:")):
                # Store current measured illumination
                data['illumination'] = int(message[13:])
            elif(message.startswith("motion:detected")):
                # Store detection
                data["detections"] += 1
            elif(message.startswith("motion:notify")):
                # If we got a message to notify, send notification email
                sendMotionAlertEmail()
            elif(message.startswith("security:on")):
                # If home security mode was turned on, save current datetime
                lastHomeSecureTimestamp = datetime.datetime.now()
            elif(message.startswith("security:off")):
                # If home security mode is off, remove start time
                lastHomeSecureTimestamp = None
            elif(message.startswith("lights:auto")):
                # If lights were set to auto, save current datetime
                lastLightAutoModeTimestamp = datetime.datetime.now()
            elif(message.startswith("lights:on") or message.startswith("lights:off")):
                # if lights is manually set, save current datetime
                lastLightAutoModeTimestamp = None
            elif(message.startswith("emergency:on")):
                # if emergency mode has been triggered, send notification email
                sendEmergencyAlertEmail()

        # Add deltaTime to homeSecureDuration
        if(lastHomeSecureTimestamp != None):
            homeSecureDuration = (datetime.datetime.now() - lastHomeSecureTimestamp).total_seconds()
            data['homeSecureModeDuration'] += homeSecureDuration
            lastHomeSecureTimestamp = datetime.datetime.now()

        # Add deltaTime to lightAutoDuration
        if(lastLightAutoModeTimestamp != None):
            lightAutoDuration = (datetime.datetime.now() - lastLightAutoModeTimestamp).total_seconds()
            data['lightAutoModeDuration'] += lightAutoDuration
            lastLightAutoModeTimestamp = datetime.datetime.now()

# Send data to ThingSpeak
def sendDataToThingSpeak(data : dict):
    while True:
        # Form URL
        url = f"{WRITE_URL}&field1={data['temperature']}&field2={data['illumination']}&field3={data['detections']}&field4={round(data['homeSecureModeDuration'])}&field5={round(data['lightAutoModeDuration'])}"

        # Send the request
        with requests.get(url) as response:
            print('ThingSpeak: Data Sent')
            # Reset values to 0
            data['detections'] = 0
            data['homeSecureModeDuration'] = 0
            data['lightAutoModeDuration'] = 0
        
        # Wait some time before sending the next request
        time.sleep(THINGSPEAK_SEND_INTERVAL)

# Read Feed from ThingSpeak
def getFeed():

    # Get the response, extract JSON and save feeds
    response = requests.get(READ_CHANNEL_URL)
    json = response.json()
    feeds = json['feeds']

    # Map feed into data object
    data = []
    for feed in feeds:
        data.append({
            "date": datetime.datetime.strptime(feed['created_at'], "%Y-%m-%dT%H:%M:%SZ"),
            "temperature": int(f) if (f := feed['field1']) != None else 0,
            "illumination": int(f) if (f := feed['field2']) != None else 0,
            "detections": int(f) if (f := feed['field3']) != None else 0,
            "homeSecureModeDuration": int(f) if (f := feed['field4']) != None else 0,
            "lightAutoModeDuration": int(f) if (f := feed['field5']) != None else 0
        })

    return data

# Send report email
def sendReportEmail():
    # Get data from ThingSpeak
    data = getFeed()

    # Create a message
    message = MIMEMultipart()

    # Create Byte buffers for storing images in memory
    temperatureGraph = io.BytesIO()
    illuminationGraph = io.BytesIO()
    detectionsGraph = io.BytesIO()

    # Array to store all data individually
    dates = []
    temperature = []
    illumination = []
    detections = []
    homeSecureModeDuration = []
    lightAutoModeDuration = []

    # Go through all data points in the feed
    for feed in data:
        # If the data point is not today, skip it
        if(feed['date'].date() != datetime.datetime.now().date()):
            continue
        
        # Extract individual data values
        dates.append(feed['date'])
        temperature.append(feed['temperature'])
        illumination.append(feed['illumination'])
        detections.append(feed['detections'])
        homeSecureModeDuration.append(feed['homeSecureModeDuration'])
        lightAutoModeDuration.append(feed['lightAutoModeDuration'])

    # Get current date
    date = datetime.datetime.now().date()

    # Calculate minimum, maximum and average temperature
    minTemperature = min(temperature)
    maxTemperature = max(temperature)
    avgTemperature = round(np.mean(temperature), 2)

    # Calculate minimum, maximum and average illumination
    minIllumination = min(illumination)
    maxIllumination = max(illumination)
    avgIllumination = round(np.mean(illumination), 2)

    # Calculate total number of detections
    totalDetections = sum(detections)

    # Calculate total number of minutes modes were turned on
    totalHomeSecureModeDuration = sum(homeSecureModeDuration) // 60
    totalLightAutoModeDuration = sum(lightAutoModeDuration) // 60

    # Create a graph for temperature
    plt.plot_date(dates, temperature, linestyle='solid', markersize=3)
    plt.title(date)
    plt.xlabel("Time")
    plt.ylabel("Temperature")
    plt.savefig(temperatureGraph, format="png")

    plt.clf()

    # Create a graph for illumination
    plt.plot_date(dates, illumination, linestyle='solid', markersize=3)
    plt.title(date)
    plt.xlabel("Time")
    plt.ylabel("Illumination")
    plt.savefig(illuminationGraph, format="png")

    plt.clf()

    # Create a graph for detections
    plt.plot_date(dates, detections, linestyle='solid', markersize=3)
    plt.title(date)
    plt.xlabel("Time")
    plt.ylabel("Detections")
    plt.savefig(detectionsGraph, format="png")

    plt.clf()

    message.preamble = "==========="

    # HTML Message to be sent
    html = f"""
        <html>
            <body>
                <h1>Report for {date}</h1>
                <h2>Temperature</h2>
                <p>Minimum: {minTemperature} &deg;C</p>
                <p>Maximum: {maxTemperature} &deg;C</p>
                <p>Average: {avgTemperature} &deg;C</p>
                <h2>Illumination</h2>
                <p>Minimum: {minIllumination} lux</p>
                <p>Maximum: {maxIllumination} lux</p>
                <p>Average: {avgIllumination} lux</p>
                <h2>Detections</h2>
                <p>Total: {totalDetections}</p>
                <h2>Home Secure Mode Duration</h2>
                <p>Total: {totalHomeSecureModeDuration} minutes</p>
                <h2>Light Auto Mode Duration</h2>
                <p>Total: {totalLightAutoModeDuration} minutes</p>
            </body>
        </html>
    """

    # Add data to the message
    message['Subject'] = "Report"
    message.attach(MIMEImage(temperatureGraph.getvalue()))
    message.attach(MIMEImage(illuminationGraph.getvalue()))
    message.attach(MIMEImage(detectionsGraph.getvalue()))
    message.attach(MIMEText(html, 'html'))

    # Send the message using SMTP
    server = smtplib.SMTP_SSL("smtp.gmail.com", 465)
    server.login(EMAIL, EMAIL_PW)
    server.sendmail(EMAIL, EMAIL, message.as_string())
    server.quit()
    print("Email: Report sent")

# Send motion alert email
def sendMotionAlertEmail():
    # Create message
    message = MIMEMultipart()
    message['Subject'] = "Motion Detected"
    server = smtplib.SMTP_SSL("smtp.gmail.com", 465)
    server.login(EMAIL, EMAIL_PW)
    server.sendmail(EMAIL, EMAIL, message.as_string())
    server.quit()
    print("Email: Motion alert sent")

# Send emergency alert
def sendEmergencyAlertEmail():
    message = MIMEMultipart()
    message['Subject'] = "Emergency Mode Activated"
    server = smtplib.SMTP_SSL("smtp.gmail.com", 465)
    server.login(EMAIL, EMAIL_PW)
    server.sendmail(EMAIL, EMAIL, message.as_string())
    server.quit()
    print("Email: Emergency alert sent")

# Check email for commands
def checkEmail(serial : Serial):

    # Create email connection
    email = imaplib.IMAP4_SSL("imap.gmail.com")
    email.login(EMAIL, EMAIL_PW)

    # Check email for new unread messages
    while True:
        email.select("inbox")
        # Send report email
        retcode, response = email.search(None, '(SUBJECT "SEND REPORT" UNSEEN)')
        if(len(response[0]) > 0):
            emailIds = response[0].split()
            # Mark emails as read
            for id in emailIds:
                email.store(id, '+FLAGS', '\\Seen')
            # Send report email
            sendReportEmail()

        # Turn off emergency mode
        retcode, response = email.search(None, '(SUBJECT "SET EMERGENCY OFF" UNSEEN)')
        if(len(response[0]) > 0):
            emailIds = response[0].split()
            # Mark emails as read
            for id in emailIds:
                email.store(id, '+FLAGS', '\\Seen')
            # Turn off emergency mode
            serial.write("emergency:off".encode('ascii'))

        # Set thermostat to auto
        retcode, response = email.search(None, '(SUBJECT "SET THERMOSTAT AUTO" UNSEEN)')
        if(len(response[0]) > 0):
            emailIds = response[0].split()
            # Mark emails as read
            for id in emailIds:
                email.store(id, '+FLAGS', '\\Seen')
            # Set thermostat to auto
            serial.write("thermostat:auto".encode('ascii'))

        # Set thermostat to heating
        retcode, response = email.search(None, '(SUBJECT "SET THERMOSTAT HEATING" UNSEEN)')
        if(len(response[0]) > 0):
            emailIds = response[0].split()
            # Mark emails as read
            for id in emailIds:
                email.store(id, '+FLAGS', '\\Seen')
            # Set thermostat to heating
            serial.write("thermostat:heating".encode('ascii'))

        # Set thermostat to cooling
        retcode, response = email.search(None, '(SUBJECT "SET THERMOSTAT COOLING" UNSEEN)')
        if(len(response[0]) > 0):
            emailIds = response[0].split()
            # Mark emails as read
            for id in emailIds:
                email.store(id, '+FLAGS', '\\Seen')
            # Set thermostat to cooling
            serial.write("thermostat:cooling".encode('ascii'))

        # Set thermostat to off
        retcode, response = email.search(None, '(SUBJECT "SET THERMOSTAT OFF" UNSEEN)')
        if(len(response[0]) > 0):
            emailIds = response[0].split()
            # Mark emails as read
            for id in emailIds:
                email.store(id, '+FLAGS', '\\Seen')
            # Set thermostat to cooling
            serial.write("thermostat:off".encode('ascii'))

        # Set lights to auto
        retcode, response = email.search(None, '(SUBJECT "SET LIGHTS AUTO" UNSEEN)')
        if(len(response[0]) > 0):
            emailIds = response[0].split()
            # Mark emails as read
            for id in emailIds:
                email.store(id, '+FLAGS', '\\Seen')
            # Set lights to auto
            serial.write("lights:auto".encode('ascii'))

        # Set lights to on
        retcode, response = email.search(None, '(SUBJECT "SET LIGHTS ON" UNSEEN)')
        if(len(response[0]) > 0):
            emailIds = response[0].split()
            # Mark emails as read
            for id in emailIds:
                email.store(id, '+FLAGS', '\\Seen')
            # Set lights to on
            serial.write("lights:on".encode('ascii'))

        # Set lights to off
        retcode, response = email.search(None, '(SUBJECT "SET LIGHTS OFF" UNSEEN)')
        if(len(response[0]) > 0):
            emailIds = response[0].split()
            # Mark emails as read
            for id in emailIds:
                email.store(id, '+FLAGS', '\\Seen')
            # Set lights to off
            serial.write("lights:off".encode('ascii'))

        # Set home security to on
        retcode, response = email.search(None, '(SUBJECT "SET HOME SECURITY ON" UNSEEN)')
        if(len(response[0]) > 0):
            emailIds = response[0].split()
            # Mark emails a read
            for id in emailIds:
                email.store(id, '+FLAGS', '\\Seen')
            # Set security to on
            serial.write("security:on".encode('ascii'))

        # Set home security to off
        retcode, response = email.search(None, '(SUBJECT "SET HOME SECURITY OFF" UNSEEN)')
        if(len(response[0]) > 0):
            emailIds = response[0].split()
            # Mark emails as read
            for id in emailIds:
                email.store(id, '+FLAGS', '\\Seen')
            # Set security to off
            serial.write("security:off".encode('ascii'))

        # Wait for some time before checking emails again
        time.sleep(EMAIL_READ_INTERVAL)

# Create a serial connection
serial = Serial(PORT, BAUD_RATE)

# Create daemon threads
readingThread = Thread(target=readSerial, args=(serial,), daemon=True)
writingThread = Thread(target=sendDataToThingSpeak, args=(data,), daemon=True)
emailThread = Thread(target=checkEmail, args=(serial,), daemon=True)

# Start threads
emailThread.start()
readingThread.start()
time.sleep(5)
writingThread.start()

# Create scheduler to send emails every day before midnight
scheduler = BackgroundScheduler()
scheduler.add_job(sendReportEmail, 'cron', hour=23, minute=59)
scheduler.start()

try:
    print("Backend: Started")
    while(True):
        pass
except KeyboardInterrupt:
    scheduler.shutdown()