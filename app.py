"""
Copyright (c) 2022 Cisco and/or its affiliates.
This software is licensed to you under the terms of the Cisco Sample
Code License, Version 1.1 (the "License"). You may obtain a copy of the
License at
               https://developer.cisco.com/docs/licenses
All use of the material herein must be in accordance with the terms of
the License. All rights not expressly granted by the License are
reserved. Unless required by applicable law or agreed to separately in
writing, software distributed under the License is distributed on an "AS
IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express
or implied.
"""

import os
import requests
import logging
import logging.config
import logging.handlers
from dotenv import load_dotenv
from datetime import datetime
from flask import Flask, render_template, jsonify, request

# Load env variables
load_dotenv()

# Flask initialization
app = Flask(__name__)
app.secret_key = os.getenv('FLASK_SECRET_KEY')

@app.context_processor
def custom_context():
    options={}
    options["SERVICE_NOW_HOST"]=os.getenv('SERVICE_NOW_HOST')
    options["SERVICE_NOW_ENDPOINT"]=os.getenv('SERVICE_NOW_ENDPOINT')
    return options

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/notify',methods=['GET','POST'])
def receive_notification():
    json_data=request.get_json()
    app.logger.debug(f'Recieved Notification Data: {json_data}')

    # Map Message and Forward
    payload=map_message(json_data["data"])
    response=forward_message_as_json(payload)

    reply_object=dict(response.json())
    reply_object["status_code"]=response.status_code
    return jsonify(reply_object)

def map_message(payload):

    # Mapping fields between SDWAN webhook notification JSON and Service Now Event Management JSON
    # * represent entire object (passed entire record in additional info for further reference or processing)
    mapping_fields={
        "message_key":"uuid",
        "source":"values",
        "em_event.metric_name":"rule_name_display",
        "type":"component",
        "severity":"severity_number",
        "description":"message",
        "time_of_event":"receive_time",
        "resolution_state":"active",
        "additional_info":"*"
    }
    records=[]
    for data in payload:
        message = {}
        for k,v in mapping_fields.items():
            if v=="*":
                message[k]=data
            elif v == "active":
                if data[v]=="true":
                    message[k] = "New"
                else:
                    message[k] = "Closing"
            elif v=="receive_time":
                message[k]=datetime.utcfromtimestamp(data[v]/1000).strftime('%Y-%m-%d %H:%M:%S')
            elif v=="values":
                list_of_devices=[]
                for device in data[v]:
                    list_of_devices.append(f'{device["host-name"]}-{device["system-ip"]}')
                message[k]=",".join(list_of_devices)
            else:
                message[k]=data[v]

        app.logger.debug(f'converted Message: {message}')
        records.append(message)

    return { "records": records }

def forward_message_as_json(payload):
    # please refer event management documentation for more info
    # https://docs.servicenow.com/en-US/bundle/tokyo-it-operations-management/page/product/event-management/task/send-events-via-web-service.html
    url = f'https://{os.getenv("SERVICE_NOW_HOST")}{os.getenv("SERVICE_NOW_ENDPOINT")}'
    headers = {
        'Accept': "application/json",
        'Content-Type': "application/json",
    }
    app.logger.debug(f'url: {url}, payload: {payload}')

    response= requests.post(url=url,headers=headers, json=payload)
    app.logger.debug(f'SNOW Response: {response.json()}')
    return response

def enable_custom_logging():

    log_path = os.getenv('LOG_PATH') if os.getenv('LOG_PATH') else "logs"
    if not os.path.exists(log_path):
        os.mkdir(log_path)

    # Standard Log File Formatting
    file_formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')

    # Timed Rotating Log File Handler, rolls over to new log at midnight
    rotating_log_handler = logging.handlers.TimedRotatingFileHandler(filename=os.path.join(log_path, 'app.log'),when='midnight', backupCount=30)
    rotating_log_handler.setFormatter(file_formatter)

    # Registering to application logger
    app.logger.addHandler(rotating_log_handler)

if __name__ == "__main__":
    # File Logging
    enable_custom_logging()
    app.run(host='0.0.0.0')