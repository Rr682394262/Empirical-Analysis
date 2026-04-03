from http.server import BaseHTTPRequestHandler, HTTPServer
import json
import threading
import time
import random
from datetime import datetime

# global registry of controllers
controllers = {}  # control_id -> Control instance

# Open the file once for appending
levels_file = open("combined.txt", "w")
file_lock = threading.Lock()  

def stop_all_controllers():
    print("Stopping all controllers...")
    for ctrl in list(controllers.values()):
        ctrl.stop()
    controllers.clear()

class Component:
    def __init__(self, name, featureTuple):
        self.name = name
        self.featureTuple = featureTuple
        self.weight = 0.0

class Control:
    def __init__(self, id, masters, slaves, components, tupleSize, mu):
        self.id = id
        self.masters = masters  
        self.slaves = slaves    
        self.components = components
        self.tupleSize = tupleSize
        self.mu = mu
        self.slaveArchWeight = {}
        self.componentWeightsMap = {c.name: [] for c in components}
        self.execution_times = []  # store execution times for trials
        self.lock = threading.Lock()
        self.stop_event = threading.Event()
        self.update_thread = None
        self.initiate_thread = None

    def stop(self):
        self.stop_event.set()
        if self.update_thread:
            self.update_thread.join()
        if self.initiate_thread:
            self.initiate_thread.join()

    def isInitiator(self):
        return not bool(self.slaves)

    def isEnder(self):
        return not bool(self.masters)

    # Receive message from a slave
    def receive_from_slave(self, slaveID, slaveArchitecture, slaveWeight, initiatorTimestamp):
        with self.lock:
            self.slaveArchWeight[slaveID] = (slaveArchitecture, slaveWeight, initiatorTimestamp)
            
            if len(self.slaveArchWeight) == len(self.slaves):
                optimalArchitectureWeight = self.chooseOptimalArchitecture(initiatorTimestamp)
                if not self.isEnder():
                    self.sendToAllMasters(optimalArchitectureWeight[0], optimalArchitectureWeight[1], initiatorTimestamp)
                else:
                    execution_time = (datetime.timestamp(datetime.now()) - initiatorTimestamp) * 1000   
                    self.execution_times.append(execution_time)
                    if len(self.execution_times) == 5:
                        avg_time = sum(self.execution_times) / len(self.execution_times)
                        print(f"OPTIMAL ARCHITECTURE: {optimalArchitectureWeight[0]}")
                        print(f"WEIGHT: {optimalArchitectureWeight[1]}")
                       
                        with file_lock:
                            levels_file.write(f"{len(list(controllers.values()))} {avg_time:.3f}\n")
                            levels_file.flush()
                        self.stop()
                        controllers.clear()                                                           

    # Compute optimal architecture
    def chooseOptimalArchitecture(self, ts):
        candidates = []
        minWeight = float('inf')

        for cname, weights in self.componentWeightsMap.items():
            # choose weight closest to timestamp
            chosenWeight = min(weights, key=lambda x: abs(x[1] - ts))[0]
            aggregated = self.slaveArchWeight[self.mu[cname]][1] + chosenWeight

            if aggregated < minWeight:
                minWeight = aggregated
                candidates = [cname]
            elif aggregated == minWeight:
                candidates.append(cname)

        optimalComponent = random.choice(candidates)
        return (self.slaveArchWeight[self.mu[optimalComponent]][0] + [optimalComponent], minWeight)

    def sendToAllMasters(self, optimalArchitectureList, optimalWeight, ts):
        for masterID in self.masters.keys():
            master = controllers.get(masterID)
            if master:
                master.receive_from_slave(
                    slaveID=self.id,
                    slaveArchitecture=optimalArchitectureList,
                    slaveWeight=optimalWeight,
                    initiatorTimestamp=ts
                )

    # Thread: Update weights periodically
    def updateWeightsLoop(self):
        while not self.stop_event.is_set():
            time.sleep(2)
            env = [random.uniform(0.0, 1.0) for _ in range(self.tupleSize)]
            for c in self.components:
                weight = sum(env[i] * c.featureTuple[i] for i in range(self.tupleSize))
                c.weight = weight
                self.componentWeightsMap[c.name].append((weight, datetime.timestamp(datetime.now())))

    # Thread: If initiator, start aggregation
    def initiateAggregationLoop(self):

        for i in range(0,5):
            if self.stop_event.is_set():
                break
            ts = datetime.timestamp(datetime.now())
            # simple: pick first component
            optimalList = [self.components[0].name]
            optimalWeight = self.componentWeightsMap[self.components[0].name][0][0]
            self.sendToAllMasters(optimalList, optimalWeight, ts)

    # Start controller threads
    def start(self):
        env = [random.uniform(0.0, 1.0) for _ in range(self.tupleSize)]
        for c in self.components:
            weight = sum(env[i] * c.featureTuple[i] for i in range(self.tupleSize))
            c.weight = weight
            self.componentWeightsMap[c.name].append((weight, datetime.timestamp(datetime.now())))
        self.update_thread = threading.Thread(target=self.updateWeightsLoop)
        self.update_thread.start()
        if self.isInitiator():
            self.initiate_thread = threading.Thread(target=self.initiateAggregationLoop)
            self.initiate_thread.start()

class ControlManager(BaseHTTPRequestHandler):
    def log_message(self, format, *args):
        pass
    
    def do_POST(self):
        
        content_len = int(self.headers.get('content-length', 0))
        data = json.loads(self.rfile.read(content_len).decode('utf-8'))

        for key, value in data.items():
            components = [Component(cid, ft) for cid, ft in value['components'].items()]
            tupleSize = len(components[0].featureTuple)
            control = Control(
                key,
                value['masters'],
                value['slaves'],
                components,
                tupleSize,
                value['mu']
            )
            controllers[key] = control
            control.start()  # start threads for this controller

        self.send_response(200)
        self.end_headers()

def run_manager_server(ip, port):
    server = HTTPServer((ip, port), ControlManager)
    print(f'Control Manager listening on {ip}:{port}')
    server.serve_forever()

if __name__ == "__main__":
    run_manager_server('127.0.0.1', 8080)
