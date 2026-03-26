from http.server import ThreadingHTTPServer, BaseHTTPRequestHandler
import json
import threading
import time
import requests
import random
from datetime import datetime

# =========================
# کلاس‌ها
# =========================

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
            return  # غیرفعال کردن چاپ خودکار HTTP

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
        optimalArchitectureList = []
        optimalWeight = float('inf')
        for compName, compWeights in componentWeightsMap.items():
            if not compWeights:
                continue
            if compWeights[-1][0] <= optimalWeight:
                optimalWeight = compWeights[-1][0]
                optimalArchitectureList = [compName]
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
            except:
                pass  # حذف چاپ خطا

    def chooseOptimalArchitecture(initiatorTimestamp):
        optimalComponent = ""
        optimalWeight = float('inf')
        for compName, compWeights in componentWeightsMap.items():
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
        return  # غیرفعال کردن چاپ خودکار HTTP

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
    ThreadingHTTPServer((ip, port), ControlManager).serve_forever()


# =========================
# بخش دوم: Host, JointSet, ArchitectureGenerator, HierarchicalControl, Deployer
# =========================

class Host:
    def __init__(self, ip, port):
        self.ip = ip
        self.port = port

class Component:
    def __init__(self, id, featureTuple):
        self.id = id    
        self.featureTuple = featureTuple

class JointSet:
    def __init__(self, jointComponents, id):
        self.id = id
        self.jointComponents = jointComponents    

    def updateDynamicMap(self, dynamic):
        for component in self.jointComponents:
            dynamic[component.id] = self.id

    def getComponentMap(self):
        map = {}
        for component in self.jointComponents: 
            map[component.id] = component.featureTuple            
        return map

class ArchitectureGenerator:
    def __init__(self): 
        self.components = {}
        self.jointSets = {}
        self.mu = {}

    def addComponent(self, component):
        self.components[component.id] = component        

    def addJointSet(self, jointSet):
        self.jointSets[jointSet.id] = jointSet        

    def addMappingToMu(self, componentId, jointSetId):
        self.mu[componentId] = jointSetId

class HierarchicalControl:
    def __init__(self, architectureGenerator, dynamic): 
        self.architectureGenerator = architectureGenerator
        self.dynamic = dynamic
        self.masters = self.createMasters()
        self.slaves = self.createSlaves()

    def createMasters(self):
        masters = {}
        for jointSetId, value in self.architectureGenerator.jointSets.items(): 
            m = set()        
            for componentId, jointSetId2 in self.architectureGenerator.mu.items():
                if jointSetId == jointSetId2: 
                    m.add(self.dynamic[componentId])            
            masters[jointSetId] = m
        return masters

    def createSlaves(self):
        slaves = {}
        for jointSetId, value in self.architectureGenerator.jointSets.items():  
            s = []    
            for jointSetId2, mastersL in self.masters.items():        
                if jointSetId in mastersL: 
                    s.append(jointSetId2)
            slaves[jointSetId] = s
        return slaves

class Deployer:
    def __init__(self, hierarchicalControl, controlManagers): 
        self.hierarchicalControl = hierarchicalControl
        self.controlManagers = controlManagers
        self.allocation = {}
        self.allocationIP = {}
        self.controlIPs = {}
        self.controlPorts = {}
        for manager in controlManagers: 
            self.allocationIP[manager.ip + ":" + str(manager.port)] = []

    def allocate(self):
        for jointSetId, jointSet in self.hierarchicalControl.architectureGenerator.jointSets.items():        
            random_index = random.randint(0, len(self.controlManagers) - 1)                            
            address = self.controlManagers[random_index].ip + ":" + str(self.controlManagers[random_index].port)
            self.allocation[jointSetId] = address
            self.allocationIP[address].append(jointSetId)
            self.controlIPs[jointSetId] = self.controlManagers[random_index].ip
            self.controlPorts[jointSetId] = self.controlManagers[random_index].port+len(self.allocationIP[address])

    def deploy(self):
        for manager in self.controlManagers:
            data = {}                                  
            for jointSetId in self.allocationIP[manager.ip + ":" + str(manager.port)]:
                data[jointSetId] = {}
                data[jointSetId]['masters'] = {}                
                for master in self.hierarchicalControl.masters[jointSetId]:                    
                    data[jointSetId]['masters'][master] = self.controlIPs[master] + ":" + str(self.controlPorts[master])
                data[jointSetId]['slaves'] = {}
                for slave in self.hierarchicalControl.slaves[jointSetId]:
                    data[jointSetId]['slaves'][slave] = self.controlIPs[slave] + ":" + str(self.controlPorts[slave])
                data[jointSetId]['components'] = self.hierarchicalControl.architectureGenerator.jointSets[jointSetId].getComponentMap()
                data[jointSetId]['mu'] = self.hierarchicalControl.architectureGenerator.mu                                           
                data[jointSetId]['port'] = self.controlPorts[jointSetId]
            try:            
                requests.post(manager.ip + ":" + str(manager.port), json=data)            
            except:
                pass  # حذف چاپ خطا

# =========================
# MAIN - محاسبه میانگین زمان
# =========================

results = []

# ورودی‌ها
h_min = int(input("MIN height (h_min): "))
h_max = int(input("MAX height (h_max): "))
d_min = int(input("MIN density (d_min): "))
d_max = int(input("MAX density (d_max): "))
trials = int(input("Enter number of trials for averaging execution time: "))

if h_min < 2 or h_max <= h_min:
    raise ValueError("Invalid h interval")
if d_max <= d_min:
    raise ValueError("Invalid d interval")

component_index = 1

def new_component():
    global component_index
    cid = f"C{component_index}"
    component_index += 1
    return Component(cid, (random.random(), random.random()))

for h in range(h_min + 1, h_max, 6):
    for d in range(d_min + 1, d_max, 6):
        trial_times = []
        for t in range(trials):
            dynamic = {}
            components = {}
            joint_sets = {}
            for i in range(1, h + 1):
                joint_id = f"O{i}"
                comps = [new_component()] if i == 1 or i == h else [new_component() for _ in range(d)]
                js = JointSet(comps, joint_id)
                js.updateDynamicMap(dynamic)
                joint_sets[joint_id] = js
                for c in comps:
                    components[c.id] = c

            generator = ArchitectureGenerator()
            for c in components.values():
                generator.addComponent(c)
            for js in joint_sets.values():
                generator.addJointSet(js)

            for i in range(1, h):
                for c in joint_sets[f"O{i}"].jointComponents:
                    generator.addMappingToMu(c.id, f"O{i+1}")
            for c in joint_sets[f"O{h}"].jointComponents:
                generator.addMappingToMu(c.id, "")

            controlStructure = HierarchicalControl(generator, dynamic)
            host1 = Host('http://127.0.0.1', 8080)
            deployer = Deployer(controlStructure, [host1])

            start_time = time.time()
            deployer.allocate()
            deployer.deploy()
            end_time = time.time()
            trial_times.append(end_time - start_time)

        avg_time = sum(trial_times) / len(trial_times)
        results.append((h, d, avg_time))

# چاپ خروجی نهایی بدون خطوط اضافی
for r in results:
    print(r)
