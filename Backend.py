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

PORT = "COM4"
BAUD_RATE = 9600

CHANNEL_ID = "2312725"
API_WRITE_KEY = "M4Y0OGXWF2CU4RI2"
API_READ_KEY = "OLV9MKWYCU5JPJXQ"

BASE_URL = "https://api.thingspeak.com"
WRITE_URL = f"{BASE_URL}/update?api_key={API_WRITE_KEY}"
READ_CHANNEL_URL = f"{BASE_URL}/channels/{CHANNEL_ID}/feeds.json?api_key={API_READ_KEY}"

READ_TEMPERATURE_URL = f"{BASE_URL}/channels/{CHANNEL_ID}/fields/1.json?api_key={API_READ_KEY}&results=50"
READ_ILLUMINATION_URL = f"{BASE_URL}/channels/{CHANNEL_ID}/fields/1.json?api_key={API_READ_KEY}&results=50"

EMAIL="iottesting8@gmail.com"
EMAIL_PW="usqidspfrqsqzodn"

THINGSPEAK_SEND_INTERVAL = 15
EMAIL_READ_INTERVAL = 5

data = {
    "temperature": 0,
    "illumination": 0,
    "detections": 0,
    "homeSecureModeDuration": 0,
    "lightAutoModeDuration": 0
}

homeSecureStartTime = None
lightAutoModeStartTime = datetime.datetime.now()

def readSerial(serial : Serial):

    global homeSecureStartTime
    global lightAutoModeStartTime

    while True:
        if serial.in_waiting > 0:

            message = serial.readline().decode('ascii')

            if(message.startswith("temperature:")):
                data['temperature'] = int(message[12:])
            elif(message.startswith("illumination:")):
                data['illumination'] = int(message[13:])
            elif(message.startswith("motion:detected")):
                data["detections"] += 1
            elif(message.startswith("motion:notify")):
                sendMotionAlertEmail()
            elif(message.startswith("security:on")):
                homeSecureStartTime = datetime.datetime.now()
            elif(message.startswith("security:off")):
                homeSecureStartTime = None
            elif(message.startswith("lights:auto")):
                lightAutoModeStartTime = datetime.datetime.now()
            elif(message.startswith("lights:on") or message.startswith("lights:off")):
                lightAutoModeStartTime = None

            print(message, end="")

        if(homeSecureStartTime != None):
            homeSecureDuration = (datetime.datetime.now() - homeSecureStartTime).total_seconds()
            data['homeSecureModeDuration'] += homeSecureDuration
            homeSecureStartTime = datetime.datetime.now()

        if(lightAutoModeStartTime != None):
            lightAutoDuration = (datetime.datetime.now() - lightAutoModeStartTime).total_seconds()
            data['lightAutoModeDuration'] += lightAutoDuration
            lightAutoModeStartTime = datetime.datetime.now()

def sendDataToThingSpeak(data : dict):
    while True:
        url = f"{WRITE_URL}&field1={data['temperature']}&field2={data['illumination']}&field3={data['detections']}&field4={round(data['homeSecureModeDuration'])}&field5={round(data['lightAutoModeDuration'])}"

        with requests.get(url) as response:
            print('Data sent')
            data['detections'] = 0
            data['homeSecureModeDuration'] = 0
            data['lightAutoModeDuration'] = 0

        time.sleep(THINGSPEAK_SEND_INTERVAL)

def getFeed():
    response = requests.get(READ_CHANNEL_URL)
    json = response.json()
    feeds = json['feeds']

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

def sendReportEmail():
    data = getFeed()

    message = MIMEMultipart()
    temperatureGraph = io.BytesIO()
    illuminationGraph = io.BytesIO()
    detectionsGraph = io.BytesIO()

    dates = []
    temperature = []
    illumination = []
    detections = []
    homeSecureModeDuration = []
    lightAutoModeDuration = []

    for feed in data:

        if(feed['date'].date() != datetime.datetime.now().date()):
            continue

        dates.append(feed['date'])
        temperature.append(feed['temperature'])
        illumination.append(feed['illumination'])
        detections.append(feed['detections'])
        homeSecureModeDuration.append(feed['homeSecureModeDuration'])
        lightAutoModeDuration.append(feed['lightAutoModeDuration'])

    date = datetime.datetime.now().date()

    minTemperature = min(temperature)
    maxTemperature = max(temperature)
    avgTemperature = np.mean(temperature)

    minIllumination = min(illumination)
    maxIllumination = max(illumination)
    avgIllumination = np.mean(illumination)

    totalDetections = sum(detections)

    totalHomeSecureModeDuration = sum(homeSecureModeDuration)
    totalLightAutoModeDuration = sum(lightAutoModeDuration)

    plt.plot_date(dates, temperature, linestyle='solid', markersize=3)
    plt.title(date)
    plt.xlabel("Time")
    plt.ylabel("Temperature")
    plt.savefig(temperatureGraph, format="png")

    plt.clf()

    plt.plot_date(dates, illumination, linestyle='solid', markersize=3)
    plt.title(date)
    plt.xlabel("Time")
    plt.ylabel("Illumination")
    plt.savefig(illuminationGraph, format="png")

    plt.clf()

    plt.plot_date(dates, detections, linestyle='solid', markersize=3)
    plt.title(date)
    plt.xlabel("Time")
    plt.ylabel("Detections")
    plt.savefig(detectionsGraph, format="png")

    plt.clf()

    message.preamble = "==========="

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
                <p>Total: {totalHomeSecureModeDuration} ms</p>
                <h2>Light Auto Mode Duration</h2>
                <p>Total: {totalLightAutoModeDuration} ms</p>
            </body>
        </html>
    """

    message['Subject'] = "Report"
    message.attach(MIMEImage(temperatureGraph.getvalue()))
    message.attach(MIMEImage(illuminationGraph.getvalue()))
    message.attach(MIMEImage(detectionsGraph.getvalue()))
    message.attach(MIMEText(html, 'html'))

    server = smtplib.SMTP_SSL("smtp.gmail.com", 465)
    server.login(EMAIL, EMAIL_PW)
    server.sendmail(EMAIL, EMAIL, message.as_string())
    server.quit()
    print("Email sent")

def sendMotionAlertEmail():
    message = MIMEMultipart()
    message['Subject'] = "Motion Detected"
    server = smtplib.SMTP_SSL("smtp.gmail.com", 465)
    server.login(EMAIL, EMAIL_PW)
    server.sendmail(EMAIL, EMAIL, message.as_string())
    server.quit()
    print("Motion alert sent")

def checkEmail(serial : Serial):
    email = imaplib.IMAP4_SSL("imap.gmail.com")
    email.login(EMAIL, EMAIL_PW)

    while True:
        email.select("inbox")
        # Send report email
        retcode, response = email.search(None, '(SUBJECT "SEND REPORT" UNSEEN)')
        if(len(response[0]) > 0):
            emailIds = response[0].split()
            for id in emailIds:
                email.store(id, '+FLAGS', '\\Seen')
            sendReportEmail()

        # Turn off emergency mode
        retcode, response = email.search(None, '(SUBJECT "SET EMERGENCY OFF" UNSEEN)')
        if(len(response[0]) > 0):
            emailIds = response[0].split()
            for id in emailIds:
                email.store(id, '+FLAGS', '\\Seen')
            serial.write("emergency:off".encode('ascii'))

        # Set thermostat to auto
        retcode, response = email.search(None, '(SUBJECT "SET THERMOSTAT AUTO" UNSEEN)')
        if(len(response[0]) > 0):
            emailIds = response[0].split()
            for id in emailIds:
                email.store(id, '+FLAGS', '\\Seen')
            serial.write("thermostat:auto".encode('ascii'))

        # Set thermostat to heating
        retcode, response = email.search(None, '(SUBJECT "SET THERMOSTAT HEATING" UNSEEN)')
        if(len(response[0]) > 0):
            emailIds = response[0].split()
            for id in emailIds:
                email.store(id, '+FLAGS', '\\Seen')
            serial.write("thermostat:heating".encode('ascii'))

        # Set thermostat to cooling
        retcode, response = email.search(None, '(SUBJECT "SET THERMOSTAT COOLING" UNSEEN)')
        if(len(response[0]) > 0):
            emailIds = response[0].split()
            for id in emailIds:
                email.store(id, '+FLAGS', '\\Seen')
            serial.write("thermostat:cooling".encode('ascii'))

        # Set thermostat to off
        retcode, response = email.search(None, '(SUBJECT "SET THERMOSTAT OFF" UNSEEN)')
        if(len(response[0]) > 0):
            emailIds = response[0].split()
            for id in emailIds:
                email.store(id, '+FLAGS', '\\Seen')
            serial.write("thermostat:off".encode('ascii'))

        # Set lights to auto
        retcode, response = email.search(None, '(SUBJECT "SET LIGHTS AUTO" UNSEEN)')
        if(len(response[0]) > 0):
            emailIds = response[0].split()
            for id in emailIds:
                email.store(id, '+FLAGS', '\\Seen')
            serial.write("lights:auto".encode('ascii'))

        # Set lights to on
        retcode, response = email.search(None, '(SUBJECT "SET LIGHTS ON" UNSEEN)')
        if(len(response[0]) > 0):
            emailIds = response[0].split()
            for id in emailIds:
                email.store(id, '+FLAGS', '\\Seen')
            serial.write("lights:on".encode('ascii'))

        # Set lights to off
        retcode, response = email.search(None, '(SUBJECT "SET LIGHTS OFF" UNSEEN)')
        if(len(response[0]) > 0):
            emailIds = response[0].split()
            for id in emailIds:
                email.store(id, '+FLAGS', '\\Seen')
            serial.write("lights:off".encode('ascii'))

        # Set home security to on
        retcode, response = email.search(None, '(SUBJECT "SET HOME SECURITY ON" UNSEEN)')
        if(len(response[0]) > 0):
            emailIds = response[0].split()
            for id in emailIds:
                email.store(id, '+FLAGS', '\\Seen')
            serial.write("security:on".encode('ascii'))

        # Set home security to off
        retcode, response = email.search(None, '(SUBJECT "SET HOME SECURITY OFF" UNSEEN)')
        if(len(response[0]) > 0):
            emailIds = response[0].split()
            for id in emailIds:
                email.store(id, '+FLAGS', '\\Seen')
            serial.write("security:off".encode('ascii'))

        time.sleep(EMAIL_READ_INTERVAL)

serial = Serial(PORT, BAUD_RATE)

readingThread = Thread(target=readSerial, args=(serial,), daemon=True)
writingThread = Thread(target=sendDataToThingSpeak, args=(data,), daemon=True)
emailThread = Thread(target=checkEmail, args=(serial,), daemon=True)

emailThread.start()
readingThread.start()
time.sleep(5)
writingThread.start()

scheduler = BackgroundScheduler()
scheduler.add_job(sendReportEmail, 'cron', hour=23, minute=59)
scheduler.start()

try:
    print("Backend started")
    while(True):
        pass
except KeyboardInterrupt:
    scheduler.shutdown()