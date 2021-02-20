# NMEA-GPS Emulator



Installation with venv
The application can be build and run locally with virtualenv tool. Run following commands in order to create virtual environment and install the required packages.
```bash
$ virtualenv venv
$ source venv/bin/activate
(venv) $ pip install -r requirements.txt
```

Output example:
```bash
$GPGGA,065835.00,5430.000,N,01920.144,E,1,04,0.92,15.2,M,32.5,M,,*65
$GPGSA,A,3,10,22,20,14,,,,,,,,,1.56,0.92,1.25*0B
$GPGSV,4,1,15,12,59,132,28,08,84,226,64,13,90,018,80,15,40,355,37*70
$GPGSV,4,2,15,30,38,303,41,16,35,337,85,09,13,089,00,20,29,100,16*78
$GPGSV,4,3,15,10,55,159,60,14,39,062,32,22,83,011,98,17,44,213,18*7F
$GPGSV,4,4,15,06,25,203,12,32,49,082,77,02,24,005,46*4B
$GPGLL,5430.000,N,01920.144,E,065835.000,A,A*5D
$GPRMC,065835.000,A,5430.000,N,01920.144,E,10.500,90.0,150221,,,A*62
$GPHDT,90.0,T*0C
$GPZDA,065835.000,15,02,2021,0,0*5C
```
