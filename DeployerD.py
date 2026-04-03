import random
import requests
import time

class Host:
    def __init__(self, ip, port):
        self.ip = ip
        self.port = port

class Component:
    def __init__(self, id, featureTuple):
        self.id = id    
        self.featureTuple = featureTuple # Preferences for n non-functional requirements

    def __str__(self):
        return f"Component {self.id}"

class JointSet:
    def __init__(self, jointComponents, id):
        self.id = id
        self.jointComponents = jointComponents    
    def updateDynamicMap(self, dynamic):
        for component in self.jointComponents: dynamic[component.id] = self.id
        return 
    def getComponentMap(self):
        map = {}
        for component in self.jointComponents: 
            map[component.id] = component.featureTuple            
        return map
    def __str__(self):
        return f"JointSet {self.id}: {self.jointComponents}"

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
                if(jointSetId == jointSetId2): m.add(self.dynamic[componentId])            
            masters[jointSetId] = m
        return masters

    def createSlaves(self):
        slaves = {}
        for jointSetId, value in self.architectureGenerator.jointSets.items():  
            s = []    
            for jointSetId2, mastersL in self.masters.items():        
                if jointSetId in mastersL: s.append(jointSetId2)
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
        self.initiatorManager = ""
        self.initiatorController = ""
        for manager in controlManagers: self.allocationIP[manager.ip + ":" + str(manager.port)] = []

    def allocate(self):
        for jointSetId, jointSet in self.hierarchicalControl.architectureGenerator.jointSets.items():        
            random_index = random.randint(0, len(self.controlManagers) - 1)                            
            address = self.controlManagers[random_index].ip + ":" + str(self.controlManagers[random_index].port)
            self.allocation[jointSetId] = address
            self.allocationIP[address].append(jointSetId)
            self.controlIPs[jointSetId] = self.controlManagers[random_index].ip
            self.controlPorts[jointSetId] = self.controlManagers[random_index].port+len(self.allocationIP[address])

    def allocate2(self):
        counter = 0
        for jointSetId, jointSet in self.hierarchicalControl.architectureGenerator.jointSets.items():        
            address = self.controlManagers[counter].ip + ":" + str(self.controlManagers[counter].port)
            self.allocation[jointSetId] = address
            self.allocationIP[address].append(jointSetId)
            self.controlIPs[jointSetId] = self.controlManagers[counter].ip
            self.controlPorts[jointSetId] = self.controlManagers[counter].port+len(self.allocationIP[address])
            counter += 1
            #print (jointSetId + "--->" + address)

    def deploy(self):
        for manager in self.controlManagers:
            data = {}                                    
            for jointSetId in self.allocationIP[manager.ip + ":" + str(manager.port)]:
                
                if(len(self.hierarchicalControl.slaves[jointSetId]) != 0):
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
                else:
                    self.initiatorManager = manager.ip + ":" + str(manager.port)
                    self.initiatorController = jointSetId
            try:            
                response = requests.post(manager.ip + ":" + str(manager.port), json=data)             
            except response.exception.requestException as e:
                print(f"An error occured: {e}")  

    def execute(self):  
        
        data = {} 
        data[self.initiatorController] = {}
        data[self.initiatorController]['masters'] = {}                
        for master in self.hierarchicalControl.masters[self.initiatorController]:                    
            data[self.initiatorController]['masters'][master] = self.controlIPs[master] + ":" + str(self.controlPorts[master])
        data[self.initiatorController]['slaves'] = {}
        for slave in self.hierarchicalControl.slaves[self.initiatorController]:
            data[self.initiatorController]['slaves'][slave] = self.controlIPs[slave] + ":" + str(self.controlPorts[slave])
        data[self.initiatorController]['components'] = self.hierarchicalControl.architectureGenerator.jointSets[self.initiatorController].getComponentMap()
        data[self.initiatorController]['mu'] = self.hierarchicalControl.architectureGenerator.mu                                           
        data[self.initiatorController]['port'] = self.controlPorts[self.initiatorController]
        try:            
            response = requests.post(self.initiatorManager, json=data)          
        except response.exception.requestException as e:
            print(f"An error occured: {e}")
            
dynamic = {}


def experiments_combined():
    print ("Conducting experiments. Please wait.")

    max_levels = 40
    max_density = 60

    for number_levels in range(3,max_levels+1,5):
        for density in range(2,max_density+1,5):
            comp_list = []
            js_list = []

            head = Component("C0", (0.5,0.7))
            top_js = JointSet([head], "O0")
            top_js.updateDynamicMap(dynamic)
            comp_list = comp_list + [head]
            js_list = js_list + [top_js]

            for j in range(1, number_levels-1): # 5 joint sets (+ top joint set + bottom joint set)
                components = []
                for c in range(density): # 5 components
                    next_component = [Component("C"+str(len(comp_list)), (0.5,0.7))]
                    components = components + next_component
                    comp_list = comp_list + next_component        
                js = JointSet(components, "O"+str(len(js_list)))
                js.updateDynamicMap(dynamic)
                js_list = js_list + [js]


            tail = Component("C"+str(len(comp_list)), (0.5,0.7))
            bottom_js = JointSet([tail], "O"+str(len(js_list)))
            bottom_js.updateDynamicMap(dynamic)
            comp_list = comp_list + [tail]
            js_list = js_list + [bottom_js]

            generator = ArchitectureGenerator()
            for c in range(len(comp_list)):
                generator.addComponent(comp_list[c])
            for j in range(len(js_list)):
                generator.addJointSet(js_list[j])

            generator.addMappingToMu("C0", "O1")
            js_counter = 2

            for cId in range(1, len(comp_list)-1):    
                generator.addMappingToMu("C"+str(cId), "O"+str(js_counter)); 
                if (cId % density == 0): js_counter += 1 # multiple of density
            generator.addMappingToMu("C"+str(len(comp_list)-1), "")

            controlStructure = HierarchicalControl(generator, dynamic)

            deployer = Deployer(controlStructure, [Host('http://127.0.0.1', 8080)])
            deployer.allocate()
            deployer.deploy()
            #time.sleep(4)
            deployer.execute()
            time.sleep(0.5) # Delay to allow the manager to free resources
    print ("Experiments completed...")

def experiments_density():
    print ("Conducting experiments. Please wait.")

    levels = 70
    max_density = 140
    for density in range(132,133,5):
        comp_list = []
        js_list = []

        head = Component("C0", (0.5,0.7))
        top_js = JointSet([head], "O0")
        top_js.updateDynamicMap(dynamic)
        comp_list = comp_list + [head]
        js_list = js_list + [top_js]

        for d in range(1, levels-1): # 5 joint sets (+ top joint set + bottom joint set)
            components = []
            for c in range(density): # 5 components
                next_component = [Component("C"+str(len(comp_list)), (0.5,0.7))]
                components = components + next_component
                comp_list = comp_list + next_component        
            js = JointSet(components, "O"+str(len(js_list)))
            js.updateDynamicMap(dynamic)
            js_list = js_list + [js]

        tail = Component("C"+str(len(comp_list)), (0.5,0.7))
        bottom_js = JointSet([tail], "O"+str(len(js_list)))
        bottom_js.updateDynamicMap(dynamic)
        comp_list = comp_list + [tail]
        js_list = js_list + [bottom_js]

        generator = ArchitectureGenerator()
        for c in range(len(comp_list)):
            generator.addComponent(comp_list[c])
        for j in range(len(js_list)):
            generator.addJointSet(js_list[j])

        generator.addMappingToMu("C0", "O1")
        js_counter = 2

        for cId in range(1, len(comp_list)-1):    
            generator.addMappingToMu("C"+str(cId), "O"+str(js_counter)); 
            if (cId % density == 0): js_counter += 1 # multiple of density
        generator.addMappingToMu("C"+str(len(comp_list)-1), "")

        controlStructure = HierarchicalControl(generator, dynamic)
        
        deployer = Deployer(controlStructure, [Host('http://127.0.0.1', 8080)])
        deployer.allocate()
        deployer.deploy()
        deployer.execute()
        time.sleep(0.5) # Delay to allow the manager to free resources
    print ("Experiments completed...")

def experiments_levels():
    print ("Conducting experiments. Please wait.")

    max_levels = 140
    density = 100
    for number_levels in range(3,max_levels+1,5):

        comp_list = []
        js_list = []

        head = Component("C0", (0.5,0.7))
        top_js = JointSet([head], "O0")
        top_js.updateDynamicMap(dynamic)
        comp_list = comp_list + [head]
        js_list = js_list + [top_js]

        for j in range(1, number_levels-1):
            components = []
            for c in range(density):
                next_component = [Component("C"+str(len(comp_list)), (0.5,0.7))]
                components = components + next_component
                comp_list = comp_list + next_component        
            js = JointSet(components, "O"+str(len(js_list)))
            js.updateDynamicMap(dynamic)
            js_list = js_list + [js]


        tail = Component("C"+str(len(comp_list)), (0.5,0.7))
        bottom_js = JointSet([tail], "O"+str(len(js_list)))
        bottom_js.updateDynamicMap(dynamic)
        comp_list = comp_list + [tail]
        js_list = js_list + [bottom_js]

        generator = ArchitectureGenerator()
        for c in range(len(comp_list)):
            generator.addComponent(comp_list[c])
        for j in range(len(js_list)):
            generator.addJointSet(js_list[j])

        generator.addMappingToMu("C0", "O1")
        js_counter = 2

        for cId in range(1, len(comp_list)-1):    
            generator.addMappingToMu("C"+str(cId), "O"+str(js_counter)); 
            if (cId % density == 0): js_counter += 1 
        generator.addMappingToMu("C"+str(len(comp_list)-1), "")

        controlStructure = HierarchicalControl(generator, dynamic)

        
        deployer = Deployer(controlStructure, [Host('http://127.0.0.1', 8080)])
        deployer.allocate()
        deployer.deploy()
        #time.sleep(4)
        deployer.execute()
        time.sleep(0.5) # Delay to allow the manager to free resources
    print ("Experiments completed...")

def experiments_vectors():
    print ("Conducting experiments. Please wait.")

    dimension = 20
    density = 5
    number_levels = 7
    # for dimension in range(2,max_dimension+1):

    comp_list = []
    js_list = []
    rnd_tuple = tuple(random.random() for _ in range(dimension))

    head = Component("C0", rnd_tuple)
    top_js = JointSet([head], "O0")
    top_js.updateDynamicMap(dynamic)
    comp_list = comp_list + [head]
    js_list = js_list + [top_js]

    for j in range(1, number_levels-1): 
        components = []
        for c in range(density): 
            next_component = [Component("C"+str(len(comp_list)), rnd_tuple)]
            components = components + next_component
            comp_list = comp_list + next_component        
        js = JointSet(components, "O"+str(len(js_list)))
        js.updateDynamicMap(dynamic)
        js_list = js_list + [js]


    tail = Component("C"+str(len(comp_list)), rnd_tuple)
    bottom_js = JointSet([tail], "O"+str(len(js_list)))
    bottom_js.updateDynamicMap(dynamic)
    comp_list = comp_list + [tail]
    js_list = js_list + [bottom_js]

    generator = ArchitectureGenerator()
    for c in range(len(comp_list)):
        generator.addComponent(comp_list[c])
    for j in range(len(js_list)):
        generator.addJointSet(js_list[j])

    generator.addMappingToMu("C0", "O1")
    js_counter = 2

    for cId in range(1, len(comp_list)-1):    
        generator.addMappingToMu("C"+str(cId), "O"+str(js_counter)); 
        if (cId % density == 0): js_counter += 1 # multiple of density
    generator.addMappingToMu("C"+str(len(comp_list)-1), "")

    controlStructure = HierarchicalControl(generator, dynamic)

    deployer = Deployer(controlStructure, [Host('http://127.0.0.1', 8080)])
    deployer.allocate()
    deployer.deploy()
    deployer.execute()
    time.sleep(0.5) # Delay to allow the manager to free resources
    print ("Experiments completed...")

experiments_levels()
