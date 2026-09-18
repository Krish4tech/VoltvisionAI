from dataclasses import dataclass
from typing import Optional
import random

V_NOMINAL = 230.0

RANGES = {
    'Fridge': (80,250), 'AC':(800,2000), 'Microwave':(800,1500),
    'LED':(5,20), 'Fan':(50,100), 'Iron':(1000,2000),
    'Toaster':(800,1500), 'EV':(1000,7400), 'Television':(60,200),
    'WiFi Router':(5,20), 'Laptop':(30,100), 'Desktop Computer':(100,500),
    'Gaming PC':(300,800), 'Washing Machine':(400,1500),
    'Electric Kettle':(1000,2500), 'Induction Stove':(1000,2500),
    'Electric Oven':(1500,3500), 'Water Heater/Geyser':(1500,3000),
    'Water Pump':(250,1500), 'Air Purifier':(20,100),
    'Room Heater':(1000,2500), 'Freezer':(100,400),
    'Coffee Maker':(600,1500), 'CCTV System':(10,50),
    'Router/Network Switch':(5,50), 'Server/NAS':(30,200),
    'Smart Display':(5,30), 'EV Battery Pre-conditioning':(500,3000),
}

@dataclass
class Appliance:    #logic
    name: str
    count: int
    active: bool
    watts: float
    def load(self): return self.count * self.watts if self.active else 0.0

@dataclass
class House:
    id: str
    appliances: dict
    connected: bool = True
    voltage: float = 0.0
    def load(self): return sum(a.load() for a in self.appliances.values())

@dataclass
class Wire:
    id: str
    a: str
    b: str
    resistance: float
    kind: str = 'MAIN'
    status: str = 'CONNECTED'
    selected: bool = False

class SWSDS:
    def __init__(self, seed=42):
        self.rng = random.Random(seed)
        self.houses = self.make_houses()
        self.wires = self.make_network()
        self.minutes = 0
        self.reset_measurements()
        self.calculate()

    def power(self, name, active=True):
        lo, hi = RANGES[name]
        return self.rng.uniform(lo, hi) if active else 0

    def make_houses(self):
        profiles = [
            [('Fridge',1,1),('AC',1,0),('LED',4,1),('Fan',2,1),('Television',1,1),('WiFi Router',1,1)],
            [('Fridge',1,1),('AC',1,1),('LED',5,1),('Fan',2,1),('Television',1,1),('WiFi Router',1,1)],
            [('Fridge',1,1),('LED',3,1),('Fan',1,1),('WiFi Router',1,1),('Laptop',1,1)],
            [('Fridge',1,1),('LED',5,1),('Fan',2,1),('EV',1,1),('WiFi Router',1,1)],
            [('Fridge',1,1),('AC',1,1),('LED',6,1),('Fan',3,1),('Television',1,1)],
            [('Fridge',1,1),('AC',1,1),('LED',5,1),('Fan',2,1),('Laptop',2,1),('Router/Network Switch',1,1)],
            [('Fridge',1,1),('LED',4,1),('Fan',2,1),('WiFi Router',1,1)],
            [('Fridge',1,1),('LED',7,1),('Fan',3,1),('Television',1,1),('Microwave',1,0)],
            [('Fridge',1,1),('AC',1,1),('LED',5,1),('Fan',2,1),('EV',1,0),('Television',1,1)],
            [('Fridge',1,1),('LED',3,1),('Fan',1,1),('WiFi Router',1,1)],
            [('Fridge',1,1),('AC',1,1),('LED',6,1),('Fan',2,1),('Electric Kettle',1,0),('Television',1,1)],
            [('Fridge',1,1),('AC',1,0),('LED',5,1),('Fan',2,1),('Laptop',1,1),('WiFi Router',1,1)],
        ]
        out={}
        for i, cfg in enumerate(profiles,1):
            apps={n:Appliance(n,c,bool(on),self.power(n,bool(on))) for n,c,on in cfg}
            out[f'HOUSE_{i:02d}']=House(f'HOUSE_{i:02d}',apps)
        return out

    def make_network(self):
        wires=[]; prev='TRANSFORMER'
        for i in range(1,13):
            sec=f'SECTION_{i:02d}'
            wires.append(Wire(f'MAIN_{i:02d}',prev,sec,0.0015+0.0001*i))
            wires.append(Wire(f'BRANCH_{i:02d}',sec,f'HOUSE_{i:02d}',0.012+0.002*(i%4),'BRANCH'))
            prev=sec
        wires += [Wire('END_SECTION','SECTION_12','V2',0.003),Wire('END_RETURN','V2','END',0.002)]
        return {w.id:w for w in wires}

    def reachable(self):
        adj={}
        for w in self.wires.values():
            if w.status!='CONNECTED': continue
            adj.setdefault(w.a,[]).append(w.b); adj.setdefault(w.b,[]).append(w.a)
        seen=set(); stack=['TRANSFORMER']
        while stack:
            n=stack.pop()
            if n in seen: continue
            seen.add(n); stack += [x for x in adj.get(n,[]) if x not in seen]
        return seen

    def reset_measurements(self):
        self.v1=self.i1=self.v2=self.i2=0.0
        self.z1=self.z2=self.dv=self.di=self.dz=None
        self.score=self.confidence=0.0; self.anomaly=False

    def calculate(self):
        old_v2=self.v2
        reach=self.reachable()
        connected={hid for hid in self.houses if hid in reach}
        for hid,h in self.houses.items(): h.connected=hid in connected
        total=sum(self.houses[hid].load() for hid in connected)
        self.v1=max(0,V_NOMINAL-(total/V_NOMINAL)*0.012)
        self.i1=total/self.v1 if self.v1 else 0
        main_r=sum(w.resistance for w in self.wires.values() if w.kind=='MAIN' and w.status=='CONNECTED')
        self.v2=max(0,self.v1-self.i1*main_r) if 'V2' in reach else 0
        self.i2=self.i1 if self.v2 > 0 else 0
        self.z1=self.v1/self.i1 if self.i1 else None
        self.z2=self.v2/self.i2 if self.i2 else None
        self.dv=abs(self.v1-self.v2); self.di=abs(self.i1-self.i2)
        self.dz=abs(self.z1-self.z2) if self.z1 is not None and self.z2 is not None else None
        voltage_score=min(1,self.dv/10)
        current_score=min(1,(self.di/max(self.i1,1e-9))/0.08) if self.i1 else 0
        impedance_score=min(1,(self.dz or 0)/0.35)
        transition_score=min(1,abs(self.v2-old_v2)/10) if old_v2 else 0
        self.score=.45*voltage_score+.25*current_score+.20*impedance_score+.10*transition_score
        self.anomaly=self.score>=.55 and (voltage_score>=.60 or current_score>=.75 or impedance_score>=.75)
        self.confidence=min(99,50+self.score*49)
        for hid,h in self.houses.items(): h.voltage=self.v2 if h.connected else 0

    def simulate_load_change(self):
        self.minutes+=2
        for h in self.houses.values():
            for a in h.appliances.values():
                # Continuous loads mostly stay stable; short-duration loads can start/stop.
                p=.08 if a.name in ('Microwave','Iron','Toaster','Electric Kettle','Coffee Maker') else .12
                if self.rng.random()<p:
                    a.active=not a.active
                    if a.active: a.watts=self.power(a.name,True)
        self.calculate()

    def select(self, wire_id):
        for w in self.wires.values(): w.selected=(w.id==wire_id and w.status=='CONNECTED')

    def snap_selected(self):
        for w in self.wires.values():
            if w.selected:
                w.status='SNAPPED'; w.selected=False; self.calculate(); return True
        return False

    def reset(self):
        self.wires=self.make_network(); self.houses=self.make_houses(); self.minutes=0; self.reset_measurements(); self.calculate()

    def report(self,title):
        connected=sum(h.connected for h in self.houses.values())
        total=sum(h.load() for h in self.houses.values() if h.connected)
        print('\n'+title)
        print('-'*60)
        print(f'Connected houses : {connected}/12')
        print(f'City load        : {total:,.1f} W')
        print(f'V1 / I1          : {self.v1:.2f} V / {self.i1:.2f} A')
        print(f'V2 / I2          : {self.v2:.2f} V / {self.i2:.2f} A')
        print(f'Z1 / Z2          : {self.z1 if self.z1 is not None else "N/A"} / {self.z2 if self.z2 is not None else "N/A"}')
        print(f'ΔV / ΔI / ΔZ     : {self.dv:.2f} / {self.di:.2f} / {self.dz if self.dz is not None else "N/A"}')
        print(f'Anomaly score    : {self.score:.3f}')
        print(f'Confidence       : {self.confidence:.1f}%')
        print('SWSDS             :', 'ANOMALY DETECTED' if self.anomaly else 'NORMAL')
        print('Disconnected      :', ', '.join(h.id for h in self.houses.values() if not h.connected) or 'None')

if __name__=='__main__':
    sim=SWSDS(seed=42)
    sim.report('1. NORMAL')
    sim.simulate_load_change()
    sim.report('2. NORMAL LOAD CHANGE')
    sim.select('MAIN_06')
    sim.snap_selected()
    sim.report('3. MAIN WIRE SNAP')
    sim.reset()
    sim.report('4. RESET')
