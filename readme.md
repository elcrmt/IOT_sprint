# Projet IoT Salle Serveur

Architecture:
ESP32 (DHT11) -> MQTT -> Raspberry Pi (pi_controller + SQLite + API Dashboard) -> MQTT -> Arduino UNO (Ethernet + buzzer + LED)

## Topics MQTT
- `salle_serveur/sensor/temperature`
- `salle_serveur/sensor/humidity`
- `salle_serveur/alarm/cmd`
- `salle_serveur/alarm/state`
- `salle_serveur/control/alarm`
- `salle_serveur/status/esp32`
- `salle_serveur/status/pi_controller`
- `salle_serveur/status/arduino`

## Cablage
### ESP32 + DHT11
- DHT11 DATA -> GPIO4
- DHT11 VCC -> 3.3V
- DHT11 GND -> GND

### Arduino UNO + Ethernet Shield + Actionneurs
- Buzzer SIG -> D6
- LED module SIG -> D8
- Buzzer VCC -> 5V
- LED module VCC -> 5V
- Buzzer GND -> GND
- LED module GND -> GND
- LED module NC -> non connecte

SPI Ethernet Shield reserve D10-D13, garder D6/D8 pour les actionneurs.

## Prerequis Raspberry Pi
- Python 3.11+
- Mosquitto actif
- `pip install -r requirements.txt`

## Configuration (.env)
Copier `.env.example` en `.env` sur le Raspberry (ex: `/home/amine/.env`) puis modifier:
- `MQTT_BROKER`
- `DB_PATH`
- `TEMP_THRESHOLD`

## Fichiers
- `pi_controller.py`: logique metier, stockage SQLite, publication commandes alarme
- `dashboard/dashboard.py`: API REST + interface web + publication commandes manuelles
- `dashboard/templates/index.html`: dashboard web
- `src/esp32.cpp`: publication capteurs
- `src/arduino.cpp`: actionneur MQTT via Ethernet

## Variables d'environnement
- `MQTT_BROKER` (defaut `10.160.24.192`)
- `MQTT_PORT` (defaut `1883`)
- `MQTT_USERNAME` (optionnel)
- `MQTT_PASSWORD` (optionnel)
- `MQTT_KEEPALIVE` (defaut `60`)
- `TEMP_THRESHOLD` (defaut `24.0`)
- `DB_PATH` (defaut `sensors.db`)

## Base de donnees SQLite
Fichier: `sensors.db` (ou chemin `DB_PATH`)

Schema:
- `measures(id, temperature, humidity, ts)`
- `alarm_events(id, source, value, ts)`

Requetes utiles:
```bash
sqlite3 sensors.db '.tables'
sqlite3 sensors.db 'select * from measures order by id desc limit 5;'
sqlite3 sensors.db 'select * from alarm_events order by id desc limit 10;'
```

## Lancement Raspberry Pi
Les scripts lisent `.env` s'il existe (par defaut a cote du script). Les services systemd peuvent aussi charger `/home/amine/.env`.

### 1) Controller
```bash
export MQTT_BROKER=127.0.0.1
export DB_PATH=/home/amine/sensors.db
python3 /home/amine/pi_controller.py
```

### 2) API + Dashboard
```bash
export MQTT_BROKER=127.0.0.1
export DB_PATH=/home/amine/sensors.db
python3 /home/amine/dashboard/dashboard.py
```

Dashboard: `http://<IP_RPI>:5000`

## Build Firmware
### ESP32
```bash
pio run -e esp32dev
pio run -e esp32dev -t upload
pio device monitor -b 115200
```

### Arduino UNO
```bash
pio run -e uno
pio run -e uno -t upload
```

## API REST
- `GET /api/latest`
- `GET /api/history?limit=20`
- `GET /api/alarm/state`
- `POST /api/alarm` payload `{"state":"ON"}` / `{"state":"OFF"}` / `{"mode":"AUTO"}`
- `GET /api/data` endpoint compatibilite dashboard legacy

Exemples:
```bash
curl -s http://127.0.0.1:5000/api/latest
curl -s http://127.0.0.1:5000/api/history?limit=5
curl -s -X POST http://127.0.0.1:5000/api/alarm -H 'Content-Type: application/json' -d '{"state":"ON"}'
```

## Tests de bout en bout
1. Demarrer Mosquitto.
2. Demarrer `pi_controller.py`.
3. Demarrer `dashboard/dashboard.py`.
4. Verifier flux capteurs:
```bash
mosquitto_sub -h 127.0.0.1 -t 'salle_serveur/sensor/#' -v
```
5. Verifier commandes alarme:
```bash
mosquitto_sub -h 127.0.0.1 -t 'salle_serveur/alarm/#' -v
```
6. Forcer ON/OFF via dashboard et verifier `salle_serveur/alarm/cmd` puis `salle_serveur/alarm/state`.

## Backup DB
```bash
mkdir -p /home/amine/backup
cp /home/amine/sensors.db "/home/amine/backup/sensors_$(date +%F_%H-%M-%S).db"
```

## Depannage
- Pas de mesures: verifier topic ESP32 (`salle_serveur/sensor/temperature`, `salle_serveur/sensor/humidity`).
- Alarme ne commute pas: verifier Arduino abonne a `salle_serveur/alarm/cmd`.
- Dashboard vide: verifier `DB_PATH` identique dans controller et dashboard.
- API inaccessible: verifier process Flask sur port 5000.

## Securite MQTT
Configuration recommandee Mosquitto:
- `allow_anonymous false`
- `password_file /etc/mosquitto/passwd`
- ACL optionnelle pour limiter publish/subscribe par client

Puis fournir `MQTT_USERNAME` et `MQTT_PASSWORD` aux scripts Python et au firmware Arduino.
