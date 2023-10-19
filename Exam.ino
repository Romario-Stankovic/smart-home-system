// Sensors and actuators

#define COOLING_RELAY 12
#define HEATING_RELAY 11

#define LIGHT 9

#define EMERGENCY_RED_LED 5
#define EMERGENCY_GREEN_LED 4
#define EMERGENCY_BUTTON 3

#define MOTION_SENSOR 2

#define LIGHT_SENSOR A0
#define TEMPERATURE_SENSOR A1

// Temperature Sensor parameters

#define TEMP_SCALE 0.01
#define TEMP_MIN 0

// Light Sensor parameters

#define R2 10000

// System parameters

#define VIN 5
#define ADR 1024

// Temperature Control System variables

bool automaticTemperatureControl = true;
bool heatingOn = false;
bool coolingOn = false;

int desiredTemperature = 20;
int temperatureDelta = 3;
long temperatureMeasuringInterval = 1000;

long lastTemperatureTimestamp = -temperatureMeasuringInterval;
long temperature = 0;

// Light Control System variables

bool automaticLightControl = true;
bool lightOn = false;
long lightMeasuringInterval = 1000;

long lastLightTimestamp = -lightMeasuringInterval;
long illumination = 0;

// Home Security System variables

long detectionInterval = 10000;

bool homeSecurityControl = false;
long lastDetectionTimestamp = -detectionInterval;

// Emergency System variables

bool emergency = false;

// System variables

long currentTimestamp;

void emergencyButtonHandler() {
    emergency = true;

    //TODO: Send email
}

void motionHandler() {

    if(!homeSecurityControl && !emergency) {
        return;
    }

    const long delta = currentTimestamp - lastDetectionTimestamp;

    if(delta > detectionInterval) {
        // TODO: Send email about detection
    }

    // TODO: Report detection to ThinkSpeak

    lastDetectionTimestamp = currentTimestamp;
}

void setup() {

    Serial.begin(9600);

    pinMode(COOLING_RELAY, OUTPUT);
    pinMode(HEATING_RELAY, OUTPUT);

    pinMode(LIGHT, OUTPUT);

    pinMode(EMERGENCY_RED_LED, OUTPUT);
    pinMode(EMERGENCY_GREEN_LED, OUTPUT);
    pinMode(EMERGENCY_BUTTON, INPUT);

    pinMode(MOTION_SENSOR, INPUT);

    pinMode(LIGHT_SENSOR, INPUT);
    pinMode(TEMPERATURE_SENSOR, INPUT);

    attachInterrupt(digitalPinToInterrupt(EMERGENCY_BUTTON), emergencyButtonHandler, RISING);
    attachInterrupt(digitalPinToInterrupt(MOTION_SENSOR), motionHandler, RISING);

}

void measureTemperature() {

    const long delta = currentTimestamp - lastTemperatureTimestamp;

    if(delta > temperatureMeasuringInterval) {
        const int temperatureRaw = analogRead(TEMPERATURE_SENSOR);

        double V_out = temperatureRaw * ((double)VIN / ADR);

        temperature = TEMP_MIN + (V_out / TEMP_SCALE);

        // TODO: Report temperature to ThingSpeak

        lastTemperatureTimestamp = currentTimestamp;

    }
}

void measureIllumination() {

    const long delta = currentTimestamp - lastLightTimestamp;

    if(delta > lightMeasuringInterval) {

        int lightRaw = analogRead(LIGHT_SENSOR);
        double V_out = lightRaw * ((double)VIN / ADR);

        const double R_ldr = ((R2 * (VIN - V_out)) / V_out);

        illumination = 500 / (R_ldr / 1000);

        //TODO: Report light to ThingSpeak

        lastLightTimestamp = currentTimestamp;

    }

}

void temperatureSystem() {

    const int min = desiredTemperature - temperatureDelta;
    const int max = desiredTemperature + temperatureDelta;

    if(automaticTemperatureControl) {

        if(temperature < min) {
            heatingOn = true;
        }

        if(temperature > max) {
            coolingOn = true;
        }

        if(temperature <= min) {
            coolingOn = false;
        }

        if(temperature >= max) {
            heatingOn = false;
        }
    }

    if(!emergency) {
        digitalWrite(HEATING_RELAY, heatingOn);
        digitalWrite(COOLING_RELAY, coolingOn);
    } else {
        digitalWrite(HEATING_RELAY, LOW);
        digitalWrite(COOLING_RELAY, LOW);
    }

}

void lightingSystem() {

    if(automaticLightControl) {
        if(illumination < 150) {
            lightOn = true;
        } else {
            lightOn = false;
        }
    }

    digitalWrite(LIGHT, lightOn);

}

void homeSecureSystem() {

    const long delta = currentTimestamp - lastDetectionTimestamp;

    if(delta > detectionInterval) {
        digitalWrite(LIGHT, LOW);
    } else {
        digitalWrite(LIGHT, HIGH);
    }

}

void loop() {

    currentTimestamp = millis();

    digitalWrite(EMERGENCY_RED_LED, emergency);
    digitalWrite(EMERGENCY_GREEN_LED, !emergency);

    if(Serial.available() > 0) {
        const String input = Serial.readString();

        if(input.startsWith("emergency:")) {
            const String value = input.substring(10);
            if(value == "off") {
                emergency = false;
            }
        }

        if(input.startsWith("temperature:")) {
            const String value = input.substring(12);
            if(value == "auto") {
                heatingOn = false;
                coolingOn = false;
                automaticTemperatureControl = true;
            } else if (value == "heating") {
                heatingOn = true;
                coolingOn = false;
                automaticTemperatureControl = false;
            } else if (value == "cooling") {
                heatingOn = false;
                coolingOn = true;
                automaticTemperatureControl = false;
            }
        }

        if(input.startsWith("light:")) {
            const String value = input.substring(6);

            if(value == "auto") {
                automaticLightControl = true;
                lightOn = false;
            } else if (value == "on") {
                automaticLightControl = false;
                lightOn = true;
            } else if (value == "off") {
                automaticLightControl = false;
                lightOn = false;
            }

        }

        if(input.startsWith("security:")) {

            const String value = input.substring(9);

            if(value == "on") {
                homeSecurityControl = true;
            } else if (value == "off") {
                homeSecurityControl = false;
            }

        }

    }

    measureTemperature();
    measureIllumination();

    if(homeSecurityControl || emergency) {
        homeSecureSystem();
    } else {
        lightingSystem();
    }

    temperatureSystem();

}