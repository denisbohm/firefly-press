#include "fd_adcm.h"
#include "fd_ble.h"
#include "fd_delay.h"
#include "fd_pwm.h"

#include "fd_nrf5.h"

#include <math.h>
#include <stdbool.h>
#include <stdint.h>

static const fd_gpio_t led1 = { .port = 0, .pin = 13 };
static const fd_gpio_t led2 = { .port = 0, .pin = 14 };
static const fd_gpio_t led3 = { .port = 0, .pin = 15 };
static const fd_gpio_t led4 = { .port = 0, .pin = 16 };
static const fd_gpio_t button1 = { .port = 0, .pin = 11 };
static const fd_gpio_t button2 = { .port = 0, .pin = 12 };
static const fd_gpio_t button3 = { .port = 0, .pin = 24 };
static const fd_gpio_t button4 = { .port = 0, .pin = 25 };

static const fd_gpio_t heater = { .port = 0, .pin = 31 };
static const fd_gpio_t thermistor = { .port = 0, .pin = 28 };

static const float adc_max_voltage = 3.0f;

static const fd_pwm_module_t pwm_modules[] = {
    { // LEDs
        .instance = 0x4001C000, // NRF_PWM0
        .frequency = 32000.0f
    },
    { // heater
        .instance = 0x40021000, // NRF_PWM1
        .frequency = 100.0f
    },
};

static const fd_pwm_module_t *led_pwm_module = &pwm_modules[0];
static const fd_pwm_module_t *heater_pwm_module = &pwm_modules[1];

static const fd_pwm_channel_t pwm_channels[] = {
    {
        .module = &pwm_modules[0],
        .instance = 0,
        .gpio = { .port = 0, .pin = 13 }, // LED1
        .polarity = fd_pwm_polarity_rising
    },
    {
        .module = &pwm_modules[1],
        .instance = 0,
        .gpio = { .port = 0, .pin = 31 }, // heater
        .polarity = fd_pwm_polarity_falling
    },
};

static const fd_pwm_channel_t *led1_pwm_channel = &pwm_channels[0];
static const fd_pwm_channel_t *heater_pwm_channel = &pwm_channels[1];

static void sleep(float duration) {
    fd_delay_ms(duration * 1000.0f);
}

static double temperature_for_resistance(double resistance) {
    // Baosity HT-NTC100K, Thermistor Model: B3950
    //
    // 21 C == 112.5 kOhm
    // 100 C == 11.93 kOhm
    // 150 C == 3.050 kOhm
    // 200 C == 1.045 kOhm
    // 250 C == 0.408 kOhm
 
    // http://www.xuru.org/rt/nlr.asp
    // limit parameters to 4
    double temperature = 203.1151903 * pow(resistance, -0.2380907273) * exp(-0.01016239151 * resistance);

    return temperature;
}

static float get_temperature(void) {
    float voltage = fd_adcm_convert(thermistor, adc_max_voltage);
    const double Vi = adc_max_voltage;
    const double Rl = 4.67;
    double resistance = Rl * (Vi / voltage - 1.0);
    return temperature_for_resistance(resistance);
}

static void set_output(float value) {
    fd_pwm_channel_start(led1_pwm_channel, value);
    fd_pwm_channel_start(heater_pwm_channel, value);
}

// ABS
//  glass transition temperature: 105 C
//  typical injection molding temperatire: 204 - 238 C
//  standard for 3D printing: 230 C

typedef struct {
    float KP;
    float KI;
    float KD;
    float iteration_time;
    float bias;
    float error_prior;
    float integral;
    float desired_value;
    bool enabled;
    float current_value;
} pid_t;

static void pid_step(pid_t *pid) {
    const float KP = pid->KP;
    const float KI = pid->KI;
    const float KD = pid->KD;
    const float iteration_time = pid->iteration_time;
    const float bias = pid->bias;
    float error_prior = pid->error_prior;
    float integral = pid->integral;
    float desired_value = pid->desired_value;
    bool enabled = pid->enabled;

    float current_value = get_temperature();
    float error = desired_value - current_value;
    integral = integral + (error * iteration_time);
    float derivative = (error - error_prior) / iteration_time;
    float output = KP * error + KI * integral + KD * derivative + bias;
    error_prior = error;

    float heat = output;
    if (heat > 1.0f) {
        heat = 1.0f;
    } else
    if (heat < 0.0f) {
        heat = 0.0f;
    }
    if (!enabled) {
        heat = 0.0f;
    }
    set_output(heat);
    uint16_t setpoint = (uint16_t)desired_value;
    uint16_t temperature = (uint16_t)current_value;
    uint8_t value[20] = {
        enabled ? 0x01 : 0x00,
        setpoint >> 0, setpoint >> 8,
        temperature >> 0, temperature >> 8,
    };
    fd_ble_set_characteristic_value(0x0002, value, sizeof(value));

    pid->current_value = current_value;
}

#include "fd_ble.h"

void fd_ble_demo_characteristic_handler(uint16_t FD_UNUSED uuid, const uint8_t *data, uint16_t length);

fd_ble_characteristic_t fd_ble_demo_characteristics[] = {
    {
        .uuid = 0x0002,
        .flags = FD_BLE_CHARACTERISTIC_FLAG_WRITE | FD_BLE_CHARACTERISTIC_FLAG_NOTIFY,
        .value_handler = fd_ble_demo_characteristic_handler
    },
    {
        .uuid = 0x0003,
        .flags = FD_BLE_CHARACTERISTIC_FLAG_WRITE_WITHOUT_RESPONSE,
        .value_handler = fd_ble_demo_characteristic_handler
    },
};

fd_ble_service_t fd_ble_demo_services[] = {
    {
        .base_uuid = { 0xB3, 0x49, 0x1D, 0x48, 0x47, 0x86, 0x79, 0x97, 0x07, 0x48, 0x3E, 0x55, 0x00, 0x00, 0x7F, 0x57 },
        .uuid = 0xB8B4,
        .characteristics = fd_ble_demo_characteristics,
        .characteristics_count = sizeof(fd_ble_demo_characteristics) / sizeof(fd_ble_demo_characteristics[0])
    },
};

pid_t pid = {
    .KP = 1.0f,
    .KI = 0.0f,
    .KD = 0.0f,
    .iteration_time = 0.1f,
    .bias = 0.0f,
    .error_prior = 0.0f,
    .integral = 0.0f,
    .desired_value = 175.0f,
    .enabled = false,
    .current_value = 0.0f,
};

void fd_ble_demo_on_tick(void) {
    pid_step(&pid);
}

fd_ble_configuration_t fd_ble_demo_configuration = {
    .name = (uint8_t *)"Firefly",
    .services = fd_ble_demo_services,
    .service_count = sizeof(fd_ble_demo_services) / sizeof(fd_ble_demo_services[0]),
    .channels = 0,
    .channel_count = 0,
    .on_tick = fd_ble_demo_on_tick
};

void fd_ble_demo_characteristic_handler(uint16_t FD_UNUSED uuid, const uint8_t *data, uint16_t length) {
    if (length < 3) {
        return;
    }
    pid.enabled = (data[0] & 0x01) != 0;
    pid.desired_value = (float)((data[2] << 8) | data[1]);
}

void main(void) {
    fd_gpio_set(led1, false);
    fd_gpio_configure_output(led1);
    fd_gpio_set(led2, true);
    fd_gpio_configure_output(led2);
    fd_gpio_set(led3, true);
    fd_gpio_configure_output(led3);
    fd_gpio_set(led4, false);
    fd_gpio_configure_output(led4);

    fd_gpio_set(heater, false);
    fd_gpio_configure_output(heater);

    fd_adcm_initialize();

    fd_pwm_initialize(pwm_modules, 2);
    fd_pwm_module_enable(led_pwm_module);
    fd_pwm_module_enable(heater_pwm_module);

    fd_ble_initialize(&fd_ble_demo_configuration);
    fd_ble_main_loop();
}
