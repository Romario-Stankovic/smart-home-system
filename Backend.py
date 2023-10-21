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
import io

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
lightAutoModeStartTime = None

def readSerial(serial : Serial):
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
                data["homeSecureModeDuration"] += datetime.datetime.now() - homeSecureStartTime
                homeSecureStartTime = None
            elif(message.startswith("lights:auto")):
                lightAutoModeStartTime = datetime.datetime.now()
            elif(message.startswith("lights:on") or message.startswith("lights:off")):
                data["lightAutoModeDuration"] += datetime.datetime.now() - lightAutoModeStartTime
                lightAutoModeStartTime = None

            print(data)

def sendDataToThingSpeak(data : dict):
    while True:
        url = f"{WRITE_URL}&field1={data['temperature']}&field2={data['illumination']}&field3={data['detections']}&field4={data['homeSecureModeDuration']}&field5={data['lightAutoModeDuration']}"

        with requests.get(url, verify=False) as response:
            print(response.text)

        time.sleep(THINGSPEAK_SEND_INTERVAL)

def getFeed():
    response = requests.get(READ_CHANNEL_URL)
    json = response.json()
    feeds = json['feeds']

    data = []

    for feed in feeds:

        data.append({
            "date": datetime.datetime.strptime(feed['created_at'], "%Y-%m-%dT%H:%M:%SZ"),
            "temperature": int(feed['field1']),
            "illumination": int(feed['field2']),
            "detections": int(feed['field3']),
            "homeSecureModeDuration": int(feed['field4']),
            "lightAutoModeDuration": int(feed['field5'])
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

        if(feed['date'].date() != datetime.datetime.now().date() - datetime.timedelta(days=1)):
            continue

        dates.append(feed['date'])
        temperature.append(feed['temperature'])
        illumination.append(feed['illumination'])
        detections.append(feed['detections'])
        homeSecureModeDuration.append(feed['homeSecureModeDuration'])
        lightAutoModeDuration.append(feed['lightAutoModeDuration'])

    date = dates[0].strftime("%d/%m/%Y")

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

    message['Message'] = "Report"
    message.attach(MIMEImage(temperatureGraph.getvalue()))
    message.attach(MIMEImage(illuminationGraph.getvalue()))
    message.attach(MIMEImage(detectionsGraph.getvalue()))

    # send body

    message['Body'] = f"Test"

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
            serial.write(b"emergency:off\n")

        # Set thermostat to auto
        retcode, response = email.search(None, '(SUBJECT "SET THERMOSTAT AUTO" UNSEEN)')
        if(len(response[0]) > 0):
            emailIds = response[0].split()
            for id in emailIds:
                email.store(id, '+FLAGS', '\\Seen')
            serial.write(b"thermostat:auto\n")

        # Set thermostat to heating
        retcode, response = email.search(None, '(SUBJECT "SET THERMOSTAT HEATING" UNSEEN)')
        if(len(response[0]) > 0):
            emailIds = response[0].split()
            for id in emailIds:
                email.store(id, '+FLAGS', '\\Seen')
            serial.write(b"thermostat:heating\n")

        # Set thermostat to cooling
        retcode, response = email.search(None, '(SUBJECT "SET THERMOSTAT COOLING" UNSEEN)')
        if(len(response[0]) > 0):
            emailIds = response[0].split()
            for id in emailIds:
                email.store(id, '+FLAGS', '\\Seen')
            serial.write(b"thermostat:cooling\n")

        # Set thermostat to off
        retcode, response = email.search(None, '(SUBJECT "SET THERMOSTAT OFF" UNSEEN)')
        if(len(response[0]) > 0):
            emailIds = response[0].split()
            for id in emailIds:
                email.store(id, '+FLAGS', '\\Seen')
            serial.write(b"thermostat:off\n")

        # Set lights to auto
        retcode, response = email.search(None, '(SUBJECT "SET LIGHTS AUTO" UNSEEN)')
        if(len(response[0]) > 0):
            emailIds = response[0].split()
            for id in emailIds:
                email.store(id, '+FLAGS', '\\Seen')
            serial.write(b"lights:auto\n")

        # Set lights to on
        retcode, response = email.search(None, '(SUBJECT "SET LIGHTS ON" UNSEEN)')
        if(len(response[0]) > 0):
            emailIds = response[0].split()
            for id in emailIds:
                email.store(id, '+FLAGS', '\\Seen')
            serial.write(b"lights:on\n")

        # Set lights to off
        retcode, response = email.search(None, '(SUBJECT "SET LIGHTS OFF" UNSEEN)')
        if(len(response[0]) > 0):
            emailIds = response[0].split()
            for id in emailIds:
                email.store(id, '+FLAGS', '\\Seen')
            serial.write(b"lights:off\n")

        # Set home security to on
        retcode, response = email.search(None, '(SUBJECT "SET HOME SECURITY ON" UNSEEN)')
        if(len(response[0]) > 0):
            emailIds = response[0].split()
            for id in emailIds:
                email.store(id, '+FLAGS', '\\Seen')
            serial.write(b"security:on\n")

        # Set home security to off
        retcode, response = email.search(None, '(SUBJECT "SET HOME SECURITY OFF" UNSEEN)')
        if(len(response[0]) > 0):
            emailIds = response[0].split()
            for id in emailIds:
                serial.write(b"security:off\n")
                email.store(id, '+FLAGS', '\\Seen')
            serial.write(b"security:off\n")

        time.sleep(EMAIL_READ_INTERVAL)

serial = Serial(PORT, BAUD_RATE)

readingThread = Thread(target=readSerial, args=(serial,), daemon=True)
writingThread = Thread(target=sendDataToThingSpeak, args=(data,), daemon=True)
emailThread = Thread(target=checkEmail, args=(serial,), daemon=True)

emailThread.start()
readingThread.start()
time.sleep(5)
writingThread.start()

while True:
    pass