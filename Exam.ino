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

#define TEMP_FACTOR 0.01  // Scale factor of the sensor (V/℃)
#define TEMP_MIN 0       // minimal temperature the sensor can measure (℃)

// Light Sensor parameters

#define R2 10000         // Known resistance of the voltage divider (Ω)
#define LIGHT_FACTOR 500  // Light factor (lux / kΩ)

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

// Handle emergency button click
void emergencyButtonHandler() {
    // Enable emergency mode
    emergency = true;

    // Send information using serial connection
    Serial.println("emergency:on");
    Serial.println("security:on");
}

// Handle motion detection
void motionHandler() {

    // Calculate delta time
    const long delta = currentTimestamp - lastDetectionTimestamp;

    // If this is our first report in some time, send a notification
    if(delta > detectionDelay) {
        Serial.println("motion:notify");
    }

    // Report that motion has been detected
    Serial.println("motion:detected");

    // Save detection timestamp
    lastDetectionTimestamp = currentTimestamp;
}

void setup() {

    // Start the serial monitor
    Serial.begin(9600);

    // Set pin modes
    pinMode(COOLING_RELAY, OUTPUT);
    pinMode(HEATING_RELAY, OUTPUT);

    pinMode(LIGHT, OUTPUT);

    pinMode(EMERGENCY_RED_LED, OUTPUT);
    pinMode(EMERGENCY_GREEN_LED, OUTPUT);
    pinMode(EMERGENCY_BUTTON, INPUT);

    pinMode(MOTION_SENSOR, INPUT);

    pinMode(LIGHT_SENSOR, INPUT);
    pinMode(TEMPERATURE_SENSOR, INPUT);

    // Attach interrupts
    attachInterrupt(digitalPinToInterrupt(EMERGENCY_BUTTON), emergencyButtonHandler, RISING);
    attachInterrupt(digitalPinToInterrupt(MOTION_SENSOR), motionHandler, RISING);

}

// Measure the temperature
void measureTemperature() {

    // Calculate time difference from last measurement
    const long delta = currentTimestamp - lastTemperatureTimestamp;

    // Check if difference is greater than interval, perform calculation
    if(delta > temperatureMeasuringInterval) {

        // Read analog signal from pin
        const int temperatureRaw = analogRead(TEMPERATURE_SENSOR);

        // Convert analog signal back into voltage
        double V_out = temperatureRaw * ((double)VIN / ADR);

        // Convert voltage into temperature
        temperature = TEMP_MIN + (V_out / TEMP_FACTOR);

        // Report read temperature
        Serial.println("temperature:" + String(temperature));

        // Save detection timestamp
        lastTemperatureTimestamp = currentTimestamp;

    }
}

// Measure illumination
void measureIllumination() {

    // Calculate time difference between last measurement
    const long delta = currentTimestamp - lastLightTimestamp;

    // Check if difference is greater than interval, perform calculation
    if(delta > lightMeasuringInterval) {

        // Read analog signal from pin
        int lightRaw = analogRead(LIGHT_SENSOR);

        // Convert analog signal back into voltage
        double V_out = lightRaw * ((double)VIN / ADR);

        // Convert voltage into Resistance on the Light Dependant Resistor (LDR)
        const double R_ldr = ((R2 * (VIN - V_out)) / V_out);

        // Calculate illumination (assuming linearity)
        illumination = LIGHT_FACTOR / (R_ldr / 1000);

        // Report read illumination
        Serial.println("illumination:" + String(illumination));

        // Save detection timestamp
        lastLightTimestamp = currentTimestamp;

    }

}

// Temperature control system
void temperatureSystem() {

    // Calculate temperature range
    const int min = desiredTemperature - temperatureDelta;
    const int max = desiredTemperature + temperatureDelta;

    // Check if automatic temperature control is on
    if(automaticTemperatureControl) {

        // If the temperature is less than min, turn on heating
        if(temperature < min) {
            heatingOn = true;
        }

        // If the temperature is more than max, turn on cooling
        if(temperature > max) {
            coolingOn = true;
        }

        // If the temperature is less or equal to min, turn off cooling
        if(temperature <= min) {
            coolingOn = false;
        }

        // If the temperature is more or equal to max, turn off heating
        if(temperature >= max) {
            heatingOn = false;
        }
    }

    if(!emergency) {
        // Normal operation
        digitalWrite(HEATING_RELAY, heatingOn);
        digitalWrite(COOLING_RELAY, coolingOn);
    } else {
        // Override
        digitalWrite(HEATING_RELAY, LOW);
        digitalWrite(COOLING_RELAY, LOW);
    }

}

// Light Control System
void lightingSystem() {

    if(automaticLightControl) {
        // Change light state if automatic control is active
        if(illumination < 150) {
            lightOn = true;
        } else {
            lightOn = false;
        }
    }

    // Normal operation
    digitalWrite(LIGHT, lightOn);

}

void homeSecureSystem() {

    // Calculate time difference between last detection
    const long delta = currentTimestamp - lastDetectionTimestamp;

    // If difference is greater than delay, turn the lights off,
    // otherwise, leave them on
    if(delta > detectionDelay) {
        digitalWrite(LIGHT, LOW);
    } else {
        digitalWrite(LIGHT, HIGH);
    }

}

// Emergency system
void emergencySystem() {
    // Turn indicators on or off
    digitalWrite(EMERGENCY_RED_LED, emergency);
    digitalWrite(EMERGENCY_GREEN_LED, !emergency);
}

void loop() {

    // Get current timestamp
    currentTimestamp = millis();

    // Check if there is input from the serial monitor
    if(Serial.available() > 0) {
        const String input = Serial.readString();

        // Control emergency mode and report back
        if(input.startsWith("emergency:")) {
            const String value = input.substring(10);
            if(value == "off") {
                emergency = false;
                Serial.println("emergency:off");
            }
        }

        // Control temperature system and report back
        if(input.startsWith("thermostat:")) {
            const String value = input.substring(12);
            if(value == "auto") {
                heatingOn = false;
                coolingOn = false;
                automaticTemperatureControl = true;
                Serial.println("thermostat:auto");
            } else if (value == "heating") {
                heatingOn = true;
                coolingOn = false;
                automaticTemperatureControl = false;
                Serial.println("thermostat:heating");
            } else if (value == "cooling") {
                heatingOn = false;
                coolingOn = true;
                automaticTemperatureControl = false;
                Serial.println("thermostat:cooling");
            }
        }

        // Control lighting system and report back
        if(input.startsWith("lights:")) {
            const String value = input.substring(6);
            if(value == "auto") {
                automaticLightControl = true;
                lightOn = false;
                Serial.println("lights:auto");
            } else if (value == "on") {
                automaticLightControl = false;
                lightOn = true;
                Serial.println("lights:on");
            } else if (value == "off") {
                automaticLightControl = false;
                lightOn = false;
                Serial.println("lights:off");
            }

        }

        // Control home security system and report back
        if(input.startsWith("security:")) {
            const String value = input.substring(9);
            if(value == "on") {
                homeSecurityControl = true;
                Serial.println("security:on");
            } else if (value == "off") {
                homeSecurityControl = false;
                Serial.println("security:off");
            }
        }

    }

    // Measure temperature and illumination
    measureTemperature();
    measureIllumination();

    // Control emergency lights
    emergencySystem();

    // Control light
    if(homeSecurityControl || emergency) {
        homeSecureSystem();
    } else {
        lightingSystem();
    }

    // Control temperature system
    temperatureSystem();

}