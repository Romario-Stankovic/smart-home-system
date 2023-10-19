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

#define TEMP_SCALE 0.01  // Scale factor of the sensor (V/℃)
#define TEMP_MIN 0       // minimal temperature the sensor can measure (℃)

// Light Sensor parameters

#define R2 10000  // Known resistance of the voltage divider (Ω)

// System parameters

#define VIN 5     // Arduino output voltage
#define ADR 1024  // Arduino ADC resolution

// Temperature Control System variables

bool automaticTemperatureControl = true;  // Is automatic control turned on
bool heatingOn = false;                   // Is the heating turned on
bool coolingOn = false;                   // Is the cooling turned on

int desiredTemperature = 20;               // Desired temperature (℃)
int temperatureDelta = 3;                  // Min and max delta values from the desired temperature (℃)

long temperatureMeasuringInterval = 600000;                     // Temperature measuring interval (ms)
long lastTemperatureTimestamp = -temperatureMeasuringInterval;  // Last measured temperature timestamp (ms)

long temperature = 0;  // Measured temperature (℃)

// Light Control System variables

bool automaticLightControl = true;  // Is automatic control turned on
bool lightOn = false;               // Is the light turned on

long lightMeasuringInterval = 600000;               // Illumination measuring interval (ms)
long lastLightTimestamp = -lightMeasuringInterval;  // Last measured light timestamp (ms)

long illumination = 0;  // Measured illumination (lux)

// Home Security System variables

long detectionDelay = 10000;  // No motion delay before the system returns to idle (ms)

bool homeSecurityControl = false;               // Is home security mode active
long lastDetectionTimestamp = -detectionDelay;  // Last detection (ms)

// Emergency System variables

bool emergency = false;  // Is emergency mode active

// System variables

long currentTimestamp;  // Current timestamp

void emergencyButtonHandler() {
    emergency = true;

    //TODO: Send email
}

void motionHandler() {

    if(!homeSecurityControl && !emergency) {
        return;
    }

    const long delta = currentTimestamp - lastDetectionTimestamp;

    if(delta > detectionDelay) {
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

    if(delta > detectionDelay) {
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