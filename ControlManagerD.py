from http.server import ThreadingHTTPServer, BaseHTTPRequestHandler
import json
import threading
import time
import requests
import random
from datetime import datetime

class Component:
    def __init__(self, name, featureTuple):
        self.name = name
        self.featureTuple = featureTuple
        self.weight = 0.0

class Control:
    def __init__(self, id, masters, slaves, ip, port, components, tupleSize, mu):
        self.id = id
        self.masters = masters
        self.slaves = slaves
        self.ip = ip
        self.port = port
        self.components = components
        self.tupleSize = tupleSize
        self.mu = mu
    def isInitiator(self):
        return not bool(self.slaves)
    def isEnder(self):
        return not bool(self.masters)
    def __str__(self):
        return f"{self.ip}:{self.port}"

def run_control_server(id, port, isInitiator, isEnder, masters, slaves, tupleSize, components, mu):

    class ControlServer(BaseHTTPRequestHandler):
        count_slaves = 0
        def log_message(self, format, *args):
            return

        def do_POST(self):
            content_len = int(self.headers.get('content-length', 0))
            post_body = self.rfile.read(content_len)
            data = json.loads(post_body.decode('utf-8'))

            slaveArchWeight[data['slaveID']] = (data['slaveArchitecture'], data['slaveWeight'], data['initiatorTimestamp'])

            self.send_response(200)
            self.send_header('Content-type', 'text/plain')
            self.end_headers()

            ControlServer.count_slaves += 1
            if ControlServer.count_slaves == len(slaves):
                optimalArchitectureWeight = chooseOptimalArchitecture(data['initiatorTimestamp'])
                if not isEnder:
                    sendToAllMasters(optimalArchitectureWeight[0], optimalArchitectureWeight[1], data['initiatorTimestamp'])
                else:
                    start_time = data['initiatorTimestamp']
                    end_time = datetime.timestamp(datetime.now())
                    execution_time = end_time - start_time
                    # ذخیره زمان در فایل برای خواندن توسط Deployer
                    with open("execution_times.txt", "a") as f:
                        f.write(f"{execution_time}\n")
                ControlServer.count_slaves = 0

    def updateWeights():
        while True:
            time.sleep(1)
            envTuple = tuple(random.random() for _ in range(tupleSize))
            for comp in components:
                comp.weight = sum(envTuple[i] * comp.featureTuple[i] for i in range(tupleSize))
                componentWeightsMap[comp.name].append((comp.weight, datetime.timestamp(datetime.now())))

    def initiateAggregation():
        time.sleep(1)
        timestamp = datetime.timestamp(datetime.now())
        # Initiator chooses component with minimum وزن
        optimalArchitectureList = []
        optimalWeight = float('inf')
        for compName, compWeights in componentWeightsMap.items():
            if not compWeights:
                continue
            if compWeights[-1][0] <= optimalWeight:
                optimalWeight = compWeights[-1][0]
                optimalArchitectureList = [compName]

# 🔴 اگر هنوز هیچ انتخابی نشده، aggregation را انجام نده
        if optimalWeight == float('inf'):
            return
        sendToAllMasters(optimalArchitectureList, optimalWeight, timestamp)

    def sendToAllMasters(optArchList, optWeight, initiatorTimestamp):
        data = {
            'slaveID': id,
            'slaveArchitecture': optArchList,
            'slaveWeight': optWeight,
            'initiatorTimestamp': initiatorTimestamp
        }
        for masterID, masterIP in masters.items():
            try:
                requests.post(masterIP, json=data)
            except Exception as e:
                print(f"Error sending to master {masterID}: {e}")

    def chooseOptimalArchitecture(initiatorTimestamp):
        optimalComponent = ""
        optimalWeight = float('inf')
        for compName, compWeights in componentWeightsMap.items():
            # انتخاب وزن نزدیک به timestamp
            chosenTimestamp = float('inf')
            for w, ts in compWeights:
                delta = abs(ts - initiatorTimestamp)
                if delta <= chosenTimestamp:
                    chosenTimestamp = delta
                    chosenWeight = w
            aggregatedWeight = slaveArchWeight[mu[compName]][1] + chosenWeight if mu[compName] in slaveArchWeight else chosenWeight
            if aggregatedWeight <= optimalWeight:
                optimalWeight = aggregatedWeight
                optimalComponent = compName
        arch = slaveArchWeight[mu[optimalComponent]][0] + [optimalComponent] if mu[optimalComponent] in slaveArchWeight else [optimalComponent]
        return (arch, optimalWeight)

    componentWeightsMap = {c.name: [] for c in components}
    slaveArchWeight = {}

    threading.Thread(target=updateWeights, daemon=True).start()
    if isInitiator:
        threading.Thread(target=initiateAggregation, daemon=True).start()

    server_address = ('', port)
    ThreadingHTTPServer(server_address, ControlServer).serve_forever()


class ControlManager(BaseHTTPRequestHandler):
    def log_message(self, format, *args):
        return

    def do_POST(self):
        content_len = int(self.headers.get('content-length', 0))
        post_body = self.rfile.read(content_len)
        data = json.loads(post_body.decode('utf-8'))

        for key, value in data.items():
            components = [Component(cid, ft) for cid, ft in value['components'].items()]
            tupleSize = len(value['components'][list(value['components'].keys())[0]])
            control = Control(key, value['masters'], value['slaves'], self.server.server_address[0], value['port'], components, tupleSize, value['mu'])
            threading.Thread(target=run_control_server, args=(control.id, control.port, control.isInitiator(), control.isEnder(), control.masters, control.slaves, control.tupleSize, control.components, control.mu), daemon=True).start()

        self.send_response(200)
        self.send_header('Content-type', 'text/plain')
        self.end_headers()


def run_manager_server(ip, port):
    print(f"Control Manager Server listening on {ip}:{port}")
    ThreadingHTTPServer((ip, port), ControlManager).serve_forever()


if __name__ == "__main__":
    run_manager_server("127.0.0.1", 8080)
