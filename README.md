NPBC ESP32 Monitor & Controller
===============================

Forum thread - https://forum.napravisam.bg/viewtopic.php?f=10&t=56132 (in Bulgarian)

A comprehensive, modern monitoring and control system for pellet burners, built on MicroPython for the ESP32 platform. This project, developed in September 2025, provides a responsive web interface, remote updates, and robust sensor integration.

Key Features
------------

* **Real-time Monitoring**: Live data from multiple sensors streamed directly to a web interface.
* **Web-Based Control**: Responsive, mobile-friendly web UI to change burner settings.
* **Remote Updates**: Secure Over-The-Air (OTA) update capability via GitHub to deploy new features and fixes.
* **Multi-Sensor Integration**: Supports temperature (DS18X20, MAX6675), and pressure/temperature/humidity (BME280/BMP280) sensors.
* **Secure Configuration**: A clear separation between public configuration (`config.py`) and private credentials (`secrets.py`).
* **Robust Architecture**: Built on an asynchronous (`uasyncio`) foundation for non-blocking, concurrent operations.
* **Remote Management**: Includes built-in FTP server and WebREPL for easy file management and debugging.


Project Overview
================

The goal of this project is to create an IoT device that interfaces directly with a pellet burner controller via UART. It collects real-time operational data such as boiler temperature, status, and pump activity.

In addition, it integrates with a suite of environmental sensors:

* **MAX6675 K-Type Thermocouple**: To measure high temperatures, typically of exhaust gases.
* **BME280/BMP280**: To measure ambient temperature, pressure, and (for the BME280) humidity.
* **DS18X20**: To measure the temperature of the returning water in the heating system.

All this data is consolidated and presented on a self-hosted web page, accessible from any device on the local network. Users can not only view the data but also send commands back to the burner to change its mode and priority.


Implementation Details
======================

Core Architecture
-----------------
The application is built entirely in MicroPython and leverages the `uasyncio` library for its core processing loop. This allows for cooperative multitasking, where data collection from sensors, communication with the burner, and handling of web server requests all occur concurrently without blocking one another.

Web Interface
-------------
The web server is powered by **Microdot**, a lightweight and efficient `asyncio`-based web framework. It serves a modern, single-page application built with HTML, CSS, and vanilla JavaScript. Key features of the frontend include:

* **Live Data**: The page automatically fetches fresh data from the ESP32 every 5 seconds.
* **Responsive Design**: The user interface adapts seamlessly to both desktop and mobile screen sizes.
* **Dark Mode**: A theme toggle allows for comfortable viewing in low-light conditions.

Hardware Interfacing
--------------------
* **Pellet Burner**: Communication is handled over a UART bus, using a custom-built protocol handler (`lib/npbc.py`) that abstracts the command and response logic.
* **Sensors**: The BME280/BMP280 and MAX6675 sensors are interfaced using the more robust **SPI** protocol. The DS18X20 sensor uses the One-Wire protocol.

Remote Management
-----------------
* **OTA Updates**: The `lib/ota.py` module enables remote application updates. It checks for new releases on a specified GitHub repository, downloads the updated files, and reboots the device.
* **FTP & WebREPL**: The project includes a built-in FTP server (`uftpd.py`) and the standard WebREPL for easy, remote access to the device's filesystem and interactive prompt for debugging.

Configuration
-------------
A dual-file system is used to manage settings securely:
* `config.py`: Contains non-sensitive application settings (pinouts, server URLs) and is safe to be included in the public repository and updated via OTA.
* `secrets.py`: Contains private credentials (WiFi password, WebREPL password). This file is created locally on the device and is **excluded** from version control and OTA updates.


Modules & Libraries
===================

Core MicroPython Libraries
--------------------------
The following libraries are required and are already included:

* `microdot`: The core web framework.
* `urequests`: Used for posting data to a remote server and by the OTA module.
* `onewire`: The protocol library for the DS18X20 sensor.
* `micropython-ds18x20`: The driver for the DS18X20 sensor.

Custom Project Modules
----------------------
* `main.py`: The main application entry point; starts all tasks and the web server.
* `boot.py`: Initializes the system on boot (WiFi, WebREPL, FTP).
* `config.py` & `secrets.py`: Handle application configuration and credentials.
* `lib/npbc.py`: The controller class for UART communication with the pellet burner.
* `lib/ota.py`: Manages the Over-The-Air update process.
* `drivers/bme280_driver.py`: A unified SPI/I2C driver for BME280 & BMP280 sensors.
* `drivers/max6675.py`: The driver for the MAX6675 thermocouple amplifier.
* `uftpd.py`: The FTP server library.


Installation
============

Follow these steps to get the project running on your ESP32 board.

1.  Hardware Setup
--------------------
Connect your sensors and the pellet burner's UART interface to the ESP32. Verify that the pins you use match the assignments in the `config.py` file.

2.  Flash MicroPython
---------------------
Flash your ESP32 with a recent, stable version of the MicroPython firmware (v1.18 or newer recommended). You can find the firmware on the `MicroPython official website <https://micropython.org/download/ESP32_GENERIC/>`_.

Use a tool like `esptool.py` to flash the firmware.

3.  Upload Project Files
------------------------
Upload all the project files and directories to the root of your ESP32's filesystem. The final structure on the device should look like this:

::

    /
    ├── uftpd.mpy
    ├── boot.py
    ├── main.py
    ├── config.py
    ├── secrets.py
    ├── lib/
    ├── drivers/
    ├── templates/
    └── static/

4.  Configure Credentials (Crucial Step)
----------------------------------------
On the ESP32, create a new file named `secrets.py` and add your private credentials. **Do not skip this step.**

::

    # secrets.py
    WIFI_SSID = 'your_wifi_ssid'
    WIFI_PASS = 'your_wifi_password'
    WEBREPL_PASS = 'your_webrepl_password'


5.  Configure the Application
-----------------------------
Review `config.py` and edit the `GITHUB_REPO` URL to point to your public GitHub repository for OTA updates. Adjust any pin assignments if your hardware setup is different.

6.  Reboot & Verify
-------------------
Reboot your ESP32. It should automatically connect to your WiFi network. Check the serial output in your terminal to see the IP address assigned to the device. You can now access the web interface by navigating to that IP address in your browser.


Usage
=====

* **Web Interface**: Access the device's IP address in a web browser to view real-time data and access the controls.
* **OTA Updates**: To update the device, push your code changes to your GitHub repository, then create a new "Release" with a version tag that matches the `version` field in your `main.json` file. The update can be triggered from the "Check for Updates" button on the web interface.


License
=======

This project is licensed under the MIT License.
