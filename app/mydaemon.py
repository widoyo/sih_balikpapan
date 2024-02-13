import logging
import sys

import daemonocle
import paho.mqtt.client as mqtt
from flask import json

from app import create_app
from app.models import Raw, Tenant


def on_connect(client, userdata, flags, rc):
    slugs = [(t.slug, 0) for t in Tenant.select()]
    client.subscribe(slugs)
    
def on_message(client, userdata, msg):
    '''
    '''
    data = json.loads(msg.payload)
    Raw._to_daily(data)
    
    
def cb_shutdown(message, code):
    logging.info('Daemon is stopping')
    logging.debug(message)

def main():
    logging.info('Daemon starting')
    client = mqtt.Client()
    client.on_connect = on_connect
    client.on_message = on_message

    client.connect("mqtt.prinus.net", 14983, 60)

    client.loop_forever()
    
def run_daemon():
    main()
    
if __name__ == '__main__':
    app = create_app()
    logging.basicConfig(filename='example.log', encoding='utf-8', level=logging.DEBUG)
    run_daemon()
