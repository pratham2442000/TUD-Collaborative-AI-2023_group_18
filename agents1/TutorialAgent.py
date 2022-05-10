import sys, random, enum, ast, time
from matrx import grid_world
from brains1.BW4TBrain import BW4TBrain
from actions1.customActions import *
from matrx import utils
from matrx.grid_world import GridWorld
from matrx.agents.agent_utils.state import State
from matrx.agents.agent_utils.navigator import Navigator
from matrx.agents.agent_utils.state_tracker import StateTracker
from matrx.actions.door_actions import OpenDoorAction
from matrx.actions.object_actions import GrabObject, DropObject, RemoveObject
from matrx.actions.move_actions import MoveNorth
from matrx.messages.message import Message
from matrx.messages.message_manager import MessageManager
from actions1.customActions import RemoveObjectTogether, CarryObjectTogether, DropObjectTogether, CarryObject, Drop

class Phase(enum.Enum):
    INTRO0=0,
    INTRO1=1,
    INTRO2=2,
    INTRO3=3,
    INTRO4=4,
    INTRO5=5,
    INTRO6=6,
    INTRO7=7,
    INTRO8=8,
    INTRO9=9,
    INTRO10=10,
    INTRO11=11,
    FIND_NEXT_GOAL=12,
    PICK_UNSEARCHED_ROOM=13,
    PLAN_PATH_TO_ROOM=14,
    FOLLOW_PATH_TO_ROOM=15,
    PLAN_ROOM_SEARCH_PATH=16,
    FOLLOW_ROOM_SEARCH_PATH=17,
    PLAN_PATH_TO_VICTIM=18,
    FOLLOW_PATH_TO_VICTIM=19,
    TAKE_VICTIM=20,
    PLAN_PATH_TO_DROPPOINT=21,
    FOLLOW_PATH_TO_DROPPOINT=22,
    DROP_VICTIM=23,
    WAIT_FOR_HUMAN=24,
    WAIT_AT_ZONE=25,
    FIX_ORDER_GRAB=26,
    FIX_ORDER_DROP=27,
    REMOVE_OBSTACLE_IF_NEEDED=28,
    ENTER_ROOM=29
    
class TutorialAgent(BW4TBrain):
    def __init__(self, condition, slowdown:int):
        super().__init__(condition, slowdown)
        self._slowdown = slowdown
        self._phase=Phase.INTRO0
        self._roomVics = []
        self._searchedRooms = []
        self._foundVictims = []
        self._collectedVictims = []
        self._foundVictimLocs = {}
        self._maxTicks = 100000
        self._sendMessages = []
        self._currentDoor=None 
        self._condition = condition
        self._providedExplanations = []   
        self._teamMembers = []

    def initialize(self):
        self._state_tracker = StateTracker(agent_id=self.agent_id)
        self._navigator = Navigator(agent_id=self.agent_id, 
            action_set=self.action_set, algorithm=Navigator.A_STAR_ALGORITHM)

    def filter_bw4t_observations(self, state):
        #self._processMessages(state)
        #for key in state.keys():
        #    print(state[key])
        return state

    def decide_on_bw4t_action(self, state:State):
        agent_name = state[self.agent_id]['obj_id']
        # Add team members
        for member in state['World']['team_members']:
            if member!=agent_name and member not in self._teamMembers:
                self._teamMembers.append(member)       
        # Process messages from team members
        self._processMessages(self._teamMembers)
        # Update trust beliefs for team members
        #self._trustBlief(self._teamMembers, receivedMessages)
        while True:           
            if Phase.INTRO0==self._phase:
                self._sendMessage('Hello! My name is RescueBot. Together we will collaborate and try to search and rescue the 8 victims on our right as quickly as possible. \
                We have to rescue the 8 victims in order from top to bottom (critically injured girl, critically injured elderly woman, critically injured man, critically injured dog, mildly injured boy, mildly injured elderly man, mildly injured woman, mildly injured cat), so it is important to only drop a victim when the previous one already has been dropped. \
                We have 10 minutes to successfully collect all 8 victims in the correct order. \
                If you understood everything I just told you, please press the "Ready!" button. We will then start our mission!', 'RescueBot')
                if self.received_messages_content and self.received_messages_content[-1]=='Ready!' or not state[{'is_human_agent':True}]:
                    self._phase=Phase.FIND_NEXT_GOAL
                else:
                    return None,{}

            if Phase.FIND_NEXT_GOAL==self._phase:
                zones = self._getDropZones(state)
                locs = [zone['location'] for zone in zones]
                self._firstVictim = str(zones[0]['img_name'])[8:-4]
                self._lastVictim = str(zones[-1]['img_name'])[8:-4]
                remainingZones = []
                for info in zones:
                    if str(info['img_name'])[8:-4] not in self._collectedVictims:
                        remainingZones.append(info)
                if remainingZones:
                    self._goalVic = str(remainingZones[0]['img_name'])[8:-4]
                    self._goalLoc = remainingZones[0]['location']
                    self._remainingZones = remainingZones
                else:
                    return None,{}

                if self._goalVic not in self._foundVictims:
                    self._phase=Phase.PICK_UNSEARCHED_ROOM
                    return Idle.__name__,{'duration_in_ticks':25}

                if self._goalVic in self._foundVictims and 'location' in self._foundVictimLocs[self._goalVic].keys():                      
                    if self._foundVictimLocs[self._goalVic]['room'] in ['area A1', 'area A2', 'area A3', 'area A4'] and state[self.agent_id]['location'] in locs and self._collectedVictims:
                        self._sendMessage('I suggest you pick up ' + self._goalVic + ' in ' + self._foundVictimLocs[self._goalVic]['room'] + ' because ' + self._foundVictimLocs[self._goalVic]['room'] + ' is far away and you can move faster. If you agree press the "Yes" button, if you do not agree press "No".', 'RescueBot')                     
                        if self.received_messages_content and self.received_messages_content[-1]=='Yes' or self._goalVic in self._collectedVictims:
                            self._collectedVictims.append(self._goalVic)
                            self._phase=Phase.FIND_NEXT_GOAL
                        if self.received_messages_content and self.received_messages_content[-1]=='No' or state['World']['nr_ticks'] > self._tick + 579:
                            self._phase=Phase.PLAN_PATH_TO_VICTIM
                        return Idle.__name__,{'duration_in_ticks':50}
                    else:
                        self._phase=Phase.PLAN_PATH_TO_VICTIM
                        return Idle.__name__,{'duration_in_ticks':50}
                        
                if self._goalVic in self._foundVictims and 'location' not in self._foundVictimLocs[self._goalVic].keys():
                    if self._foundVictimLocs[self._goalVic]['room'] in ['area A1', 'area A2', 'area A3', 'area A4'] and state[self.agent_id]['location'] in locs and self._collectedVictims:
                        self._sendMessage('I suggest you pick up ' + self._goalVic + ' in ' + self._foundVictimLocs[self._goalVic]['room'] + ' because ' + self._foundVictimLocs[self._goalVic]['room'] + ' is far away and you can move faster. If you agree press the "Yes" button, if you do not agree press "No".', 'RescueBot')
                        if self.received_messages_content and self.received_messages_content[-1]=='Yes' or self._goalVic in self._collectedVictims:
                            self._collectedVictims.append(self._goalVic)
                            self._phase=Phase.FIND_NEXT_GOAL
                        if self.received_messages_content and self.received_messages_content[-1]=='No' or state['World']['nr_ticks'] > self._tick + 579:
                            self._phase=Phase.PLAN_PATH_TO_ROOM
                        return Idle.__name__,{'duration_in_ticks':50}
                    else:
                        self._phase=Phase.PLAN_PATH_TO_ROOM
                        return Idle.__name__,{'duration_in_ticks':50}                    

            if Phase.PICK_UNSEARCHED_ROOM==self._phase:
                agent_location = state[self.agent_id]['location']
                unsearchedRooms=[room['room_name'] for room in state.values()
                if 'class_inheritance' in room
                and 'Door' in room['class_inheritance']
                and room['room_name'] not in self._searchedRooms]
                if self._remainingZones and len(unsearchedRooms) == 0:
                    self._searchedRooms = []
                    self._sendMessages = []
                    self.received_messages = []
                    self.received_messages_content = []
                    self._searchedRooms.append(self._door['room_name'])
                    self._sendMessage('Going to re-search all areas because we searched all areas but did not find ' + self._goalVic,'RescueBot')
                    self._phase = Phase.FIND_NEXT_GOAL
                else:
                    if self._currentDoor==None:
                        self._door = state.get_room_doors(self._getClosestRoom(state,unsearchedRooms,agent_location))[0]
                        self._doormat = state.get_room(self._getClosestRoom(state,unsearchedRooms,agent_location))[-1]['doormat']
                        if self._door['room_name'] == 'area 1':
                            self._doormat = (3,5)
                        self._phase = Phase.PLAN_PATH_TO_ROOM
                    if self._currentDoor!=None:
                        self._door = state.get_room_doors(self._getClosestRoom(state,unsearchedRooms,self._currentDoor))[0]
                        self._doormat = state.get_room(self._getClosestRoom(state, unsearchedRooms,self._currentDoor))[-1]['doormat']
                        if self._door['room_name'] == 'area 1':
                            self._doormat = (3,5)
                        self._phase = Phase.PLAN_PATH_TO_ROOM

            if Phase.PLAN_PATH_TO_ROOM==self._phase:
                self._navigator.reset_full()
                if self._goalVic in self._foundVictims and 'location' not in self._foundVictimLocs[self._goalVic].keys():
                    self._door = state.get_room_doors(self._foundVictimLocs[self._goalVic]['room'])[0]
                    self._doormat = state.get_room(self._foundVictimLocs[self._goalVic]['room'])[-1]['doormat']
                    #doorLoc = self._door['location']
                    doorLoc = self._doormat
                else:
                    #doorLoc = self._door['location']
                    doorLoc = self._doormat
                self._navigator.add_waypoints([doorLoc])
                self._phase=Phase.FOLLOW_PATH_TO_ROOM

            if Phase.FOLLOW_PATH_TO_ROOM==self._phase:
                if self._goalVic in self._collectedVictims:
                    self._currentDoor=None
                    self._phase=Phase.FIND_NEXT_GOAL
                if self._goalVic in self._foundVictims and self._door['room_name']!=self._foundVictimLocs[self._goalVic]['room']:
                    self._currentDoor=None
                    self._phase=Phase.FIND_NEXT_GOAL
                if self._door['room_name'] in self._searchedRooms and self._goalVic not in self._foundVictims:
                    self._currentDoor=None
                    self._phase=Phase.FIND_NEXT_GOAL
                else:
                    self._state_tracker.update(state)
                    if self._goalVic in self._foundVictims and str(self._door['room_name']) == self._foundVictimLocs[self._goalVic]['room']:
                        self._sendMessage('Moving to ' + str(self._door['room_name']) + ' to pick up ' + self._goalVic+'.', 'RescueBot')                 
                    if self._goalVic not in self._foundVictims:
                        self._sendMessage('Moving to ' + str(self._door['room_name']) + ' to search for ' + self._goalVic + ' and because it is the closest unsearched area.', 'RescueBot')                   
                    self._currentDoor=self._door['location']
                    #self._currentDoor=self._doormat
                    action = self._navigator.get_move_action(self._state_tracker)
                    if action!=None:
                        return action,{}
                    #self._phase=Phase.PLAN_ROOM_SEARCH_PATH
                    self._phase=Phase.REMOVE_OBSTACLE_IF_NEEDED
                    return Idle.__name__,{'duration_in_ticks':50}         

            

            if Phase.REMOVE_OBSTACLE_IF_NEEDED==self._phase:
                objects = []
                agent_location = state[self.agent_id]['location']
                for info in state.values():
                    if 'class_inheritance' in info and 'ObstacleObject' in info['class_inheritance'] and 'rock' in info['obj_id']:
                        objects.append(info)
                        self._sendMessage('Please come to the entrance of ' + str(self._door['room_name']) + ' because I am unable to remove this rock alone.', 'RescueBot')
                        if not 'Human' in info['name']:
                        #if not state[{'is_human_agent':True}]:
                            #self._sendMessage('Waiting..','RescueBot')
                            return None, {} 
                    if 'class_inheritance' in info and 'ObstacleObject' in info['class_inheritance'] and 'tree' in info['obj_id']:
                        objects.append(info)
                        self._sendMessage('Removing the tree blocking the entrance of ' + str(self._door['room_name']) + ' because I want to search this area.', 'RescueBot')
                        self._phase = Phase.ENTER_ROOM
                        return RemoveObject.__name__,{'object_id':info['obj_id']}
                    if 'class_inheritance' in info and 'ObstacleObject' in info['class_inheritance'] and 'stone' in info['obj_id']:
                        objects.append(info)
                        self._sendMessage('Removing the stones blocking the entrance of ' + str(self._door['room_name']) + ' because I want to search this area. We can remove them faster if you help me', 'RescueBot')
                        self._phase = Phase.ENTER_ROOM
                        return RemoveObject.__name__,{'object_id':info['obj_id']}
                if len(objects)==0:                    
                    #self._sendMessage('No need to clear the entrance of ' + str(self._door['room_name']) + ' because it is not blocked by obstacles.','RescueBot')
                    self._phase = Phase.ENTER_ROOM
                    
            if Phase.ENTER_ROOM==self._phase:
                if self._goalVic in self._collectedVictims:
                    self._currentDoor=None
                    self._phase=Phase.FIND_NEXT_GOAL
                if self._goalVic in self._foundVictims and self._door['room_name']!=self._foundVictimLocs[self._goalVic]['room']:
                    self._currentDoor=None
                    self._phase=Phase.FIND_NEXT_GOAL
                if self._door['room_name'] in self._searchedRooms and self._goalVic not in self._foundVictims:
                    self._currentDoor=None
                    self._phase=Phase.FIND_NEXT_GOAL
                else:
                    self._state_tracker.update(state)                 
                    #self._currentDoor=self._door['location']
                    #self._currentDoor=self._door
                    action = self._navigator.get_move_action(self._state_tracker)
                    if action!=None:
                        return action,{}
                    self._phase=Phase.PLAN_ROOM_SEARCH_PATH
                    #self._phase=Phase.REMOVE_OBSTACLE_IF_NEEDED
                    return Idle.__name__,{'duration_in_ticks':50} 


            if Phase.PLAN_ROOM_SEARCH_PATH==self._phase:
                roomTiles = [info['location'] for info in state.values()
                    if 'class_inheritance' in info 
                    and 'AreaTile' in info['class_inheritance']
                    and 'room_name' in info
                    and info['room_name'] == self._door['room_name']
                ]
                self._roomtiles=roomTiles               
                self._navigator.reset_full()
                self._navigator.add_waypoints(self._efficientSearch(roomTiles))
                self._sendMessage('Searching through whole ' + str(self._door['room_name']) + ' because my sense range is limited and to find ' + self._goalVic+'.', 'RescueBot')
                #self._currentDoor = self._door['location']
                self._roomVics=[]
                self._phase=Phase.FOLLOW_ROOM_SEARCH_PATH
                return Idle.__name__,{'duration_in_ticks':50}

            if Phase.FOLLOW_ROOM_SEARCH_PATH==self._phase:
                self._state_tracker.update(state)
                action = self._navigator.get_move_action(self._state_tracker)
                if action!=None:
                    
                    for info in state.values():
                        if 'class_inheritance' in info and 'CollectableBlock' in info['class_inheritance']:
                            vic = str(info['img_name'][8:-4])
                            if vic not in self._roomVics:
                                self._roomVics.append(vic)

                            if vic in self._foundVictims and 'location' not in self._foundVictimLocs[vic].keys():
                                self._foundVictimLocs[vic] = {'location':info['location'],'room':self._door['room_name'],'obj_id':info['obj_id']}
                                if vic == self._goalVic:
                                    self._sendMessage('Found '+ vic + ' in ' + self._door['room_name'] + ' because you told me '+vic+ ' was located here.', 'RescueBot')
                                    self._searchedRooms.append(self._door['room_name'])
                                    self._phase=Phase.FIND_NEXT_GOAL

                            if 'healthy' not in vic and vic not in self._foundVictims:
                                self._sendMessage('Found '+ vic + ' in ' + self._door['room_name'] + ' because I am traversing the whole area.', 'RescueBot')
                                self._foundVictims.append(vic)
                                self._foundVictimLocs[vic] = {'location':info['location'],'room':self._door['room_name'],'obj_id':info['obj_id']}
                    return action,{}
                #if self._goalVic not in self._foundVictims:
                #    self._sendMessage(self._goalVic + ' not present in ' + str(self._door['room_name']) + ' because I searched the whole area without finding ' + self._goalVic, 'RescueBot')
                if self._goalVic in self._foundVictims and self._goalVic not in self._roomVics and self._foundVictimLocs[self._goalVic]['room']==self._door['room_name']:
                    self._sendMessage(self._goalVic + ' not present in ' + str(self._door['room_name']) + ' because I searched the whole area without finding ' + self._goalVic+'.', 'RescueBot')
                    self._foundVictimLocs.pop(self._goalVic, None)
                    self._foundVictims.remove(self._goalVic)
                    self._roomVics = []
                    self.received_messages = []
                    self.received_messages_content = []
                self._searchedRooms.append(self._door['room_name'])
                self._phase=Phase.FIND_NEXT_GOAL
                return Idle.__name__,{'duration_in_ticks':50}
                
            if Phase.PLAN_PATH_TO_VICTIM==self._phase:
                if 'mild' in self._goalVic:
                    self._sendMessage('Picking up ' + self._goalVic + ' in ' + self._foundVictimLocs[self._goalVic]['room'] + ' because ' + self._goalVic + ' should be transported to the drop zone.', 'RescueBot')
                self._navigator.reset_full()
                self._navigator.add_waypoints([self._foundVictimLocs[self._goalVic]['location']])
                self._phase=Phase.FOLLOW_PATH_TO_VICTIM
                return Idle.__name__,{'duration_in_ticks':50}
                    
            if Phase.FOLLOW_PATH_TO_VICTIM==self._phase:
                if self._goalVic in self._collectedVictims:
                    self._phase=Phase.FIND_NEXT_GOAL
                else:
                    self._state_tracker.update(state)
                    action=self._navigator.get_move_action(self._state_tracker)
                    if action!=None:
                        return action,{}
                    if action==None and 'critical' in self._goalVic:
                        self._phase=Phase.TAKE_VICTIM
                        return MoveNorth.__name__, {}
                    
            if Phase.TAKE_VICTIM==self._phase:
                objects=[]
                for info in state.values():
                    if 'class_inheritance' in info and 'CollectableBlock' in info['class_inheritance'] and 'critical' in info['obj_id']:
                        objects.append(info)
                        self._sendMessage('Please come to ' + str(self._door['room_name']) + ' because we need to carry ' + str(self._goalVic) + ' together.', 'RescueBot')
                        if not 'Human' in info['name']:
                        #if not state[{'is_human_agent':True}]:
                            #self._sendMessage('Waiting..','RescueBot')
                            return None, {} 
                if len(objects)==0:
                    self._phase = Phase.PLAN_PATH_TO_DROPPOINT
                    self._collectedVictims.append(self._goalVic)
                if 'mild' in self._goalVic:
                    self._phase=Phase.PLAN_PATH_TO_DROPPOINT
                    self._collectedVictims.append(self._goalVic)
                    return CarryObject.__name__,{'object_id':self._foundVictimLocs[self._goalVic]['obj_id']}                

            if Phase.PLAN_PATH_TO_DROPPOINT==self._phase:
                self._navigator.reset_full()
                self._navigator.add_waypoints([self._goalLoc])
                self._phase=Phase.FOLLOW_PATH_TO_DROPPOINT

            if Phase.FOLLOW_PATH_TO_DROPPOINT==self._phase:
                #self._sendMessage('Transporting '+ self._goalVic + ' to the drop zone because ' + self._goalVic + ' should be delivered there for further treatment.', 'RescueBot')
                self._state_tracker.update(state)
                action=self._navigator.get_move_action(self._state_tracker)
                if action!=None:
                    return action,{}
                self._phase=Phase.DROP_VICTIM
                #return Idle.__name__,{'duration_in_ticks':50}  

            if Phase.DROP_VICTIM == self._phase:
                zones = self._getDropZones(state)
                for i in range(len(zones)):
                    if zones[i]['img_name'][8:-4]==self._goalVic:
                        if self._goalVic!=self._firstVictim:
                            self._previousVic = zones[i-1]['img_name']
                        if self._goalVic!=self._lastVictim:
                            self._nextVic = zones[i+1]['img_name']

                if self._goalVic==self._firstVictim or state[{'img_name':self._previousVic,'is_collectable':True}] and self._goalVic==self._lastVictim or state[{'img_name':self._previousVic, 'is_collectable':True}] and not state[{'img_name':self._nextVic, 'is_collectable':True}]:
                    if 'mild' in self._goalVic:
                        self._sendMessage('Delivered '+ self._goalVic + ' at the drop zone because ' + self._goalVic + ' was the current victim to rescue.', 'RescueBot')
                    self._phase=Phase.FIND_NEXT_GOAL
                    self._currentDoor = None
                    self._tick = state['World']['nr_ticks']
                    return Drop.__name__,{}
                #if state[{'img_name':self._nextVic, 'is_collectable':True}] and state[{'img_name':self._previousVic, 'is_collectable':True}]:
                #    self._sendMessage('Delivered '+ self._goalVic + ' at the drop zone because ' + self._goalVic + ' was the current victim to rescue.', 'RescueBot')
                #    self._phase=Phase.FIX_ORDER_GRAB
                #    return DropObject.__name__,{}
                else:
                    self._sendMessage('Waiting for human operator at drop zone because previous victim should be collected first.', 'RescueBot')
                    return None,{} 

            #if Phase.FIX_ORDER_GRAB == self._phase:
            #    self._navigator.reset_full()
            #    self._navigator.add_waypoints([state[{'img_name':self._nextVic, 'is_collectable':True}]['location']])
            #    self._state_tracker.update(state)
            #    action=self._navigator.get_move_action(self._state_tracker)
            #    if action!=None:
            #        return action,{}
            #    self._phase=Phase.FIX_ORDER_DROP
            #    return GrabObject.__name__,{'object_id':state[{'img_name':self._nextVic, 'is_collectable':True}]['obj_id']}
                
            #if Phase.FIX_ORDER_DROP==self._phase:
            #    self._phase=Phase.FIND_NEXT_GOAL
            #    self._tick = state['World']['nr_ticks']
            #    return DropObject.__name__,{}   

            
    def _getDropZones(self,state:State):
        '''
        @return list of drop zones (their full dict), in order (the first one is the
        the place that requires the first drop)
        '''
        places=state[{'is_goal_block':True}]
        places.sort(key=lambda info:info['location'][1])
        zones = []
        for place in places:
            if place['drop_zone_nr']==0:
                zones.append(place)
        return zones

    def _processMessages(self, teamMembers):
        '''
        process incoming messages. 
        Reported blocks are added to self._blocks
        '''
        receivedMessages = {}
        for member in teamMembers:
            receivedMessages[member] = []
        for mssg in self.received_messages:
            for member in teamMembers:
                if mssg.from_id == member:
                    receivedMessages[member].append(mssg.content) 
        #areas = ['area A1','area A2','area A3','area A4','area B1','area B2','area C1','area C2','area C3']
        for mssgs in receivedMessages.values():
            for msg in mssgs:
                if msg.startswith("Search:"):
                    area = 'area '+ msg.split()[-1]
                    if area not in self._searchedRooms:
                        self._searchedRooms.append(area)
                if msg.startswith("Found:"):
                    if len(msg.split()) == 6:
                        foundVic = ' '.join(msg.split()[1:4])
                    else:
                        foundVic = ' '.join(msg.split()[1:5]) 
                    loc = 'area '+ msg.split()[-1]
                    print(loc)
                    if loc not in self._searchedRooms:
                        self._searchedRooms.append(loc)
                    if foundVic not in self._foundVictims:
                        self._foundVictims.append(foundVic)
                        self._foundVictimLocs[foundVic] = {'room':loc}
                    if foundVic in self._foundVictims and self._foundVictimLocs[foundVic]['room'] != loc:
                        self._foundVictimLocs[foundVic] = {'room':loc}
                if msg.startswith('Collect:'):
                    if len(msg.split()) == 6:
                        collectVic = ' '.join(msg.split()[1:4])
                    else:
                        collectVic = ' '.join(msg.split()[1:5]) 
                    loc = 'area ' + msg.split()[-1]
                    if loc not in self._searchedRooms:
                        self._searchedRooms.append(loc)
                    if collectVic not in self._foundVictims:
                        self._foundVictims.append(collectVic)
                        self._foundVictimLocs[collectVic] = {'room':loc}
                    if collectVic in self._foundVictims and self._foundVictimLocs[collectVic]['room'] != loc:
                        self._foundVictimLocs[collectVic] = {'room':loc}
                    if collectVic not in self._collectedVictims:
                        self._collectedVictims.append(collectVic)
            #if msg.startswith('Mission'):
            #    self._sendMessage('Unsearched areas: '  + ', '.join([i.split()[1] for i in areas if i not in self._searchedRooms]) + '. Collected victims: ' + ', '.join(self._collectedVictims) +
            #    '. Found victims: ' +  ', '.join([i + ' in ' + self._foundVictimLocs[i]['room'] for i in self._foundVictimLocs]) ,'RescueBot')
            #    self.received_messages=[]

    def _trustBlief(self, member, received):
        '''
        Baseline implementation of a trust belief. Creates a dictionary with trust belief scores for each team member, for example based on the received messages.
        '''
        default = 0.5
        trustBeliefs = {}
        for member in received.keys():
            trustBeliefs[member] = default
        for member in received.keys():
            for message in received[member]:
                if 'Found' in message and 'colour' not in message:
                    trustBeliefs[member]-=0.1
                    break
        return trustBeliefs

    def _sendMessage(self, mssg, sender):
        msg = Message(content=mssg, from_id=sender)
        if msg.content not in self.received_messages_content:
            self.send_message(msg)
            self._sendMessages.append(msg.content)

        #if self.received_messages and self._sendMessages:
        #    self._last_mssg = self._sendMessages[-1]
        #    if self._last_mssg.startswith('Searching') or self._last_mssg.startswith('Moving'):
        #        self.received_messages=[]
        #        self.received_messages.append(self._last_mssg)

    def _getClosestRoom(self, state, objs, currentDoor):
        agent_location = state[self.agent_id]['location']
        locs = {}
        for obj in objs:
            locs[obj]=state.get_room_doors(obj)[0]['location']
        dists = {}
        for room,loc in locs.items():
            if currentDoor!=None:
                dists[room]=utils.get_distance(currentDoor,loc)
            if currentDoor==None:
                dists[room]=utils.get_distance(agent_location,loc)

        return min(dists,key=dists.get)

    def _efficientSearch(self, tiles):
        x=[]
        y=[]
        for i in tiles:
            if i[0] not in x:
                x.append(i[0])
            if i[1] not in y:
                y.append(i[1])
        locs = []
        for i in range(len(x)):
            if i%2==0:
                locs.append((x[i],min(y)))
            else:
                locs.append((x[i],max(y)))
        return locs

    def _dynamicMessage(self, mssg1, mssg2, explanation, sender):
        if explanation not in self._providedExplanations:
            self._sendMessage(mssg1,sender)
            self._providedExplanations.append(explanation)
        if 'Searching' in mssg1:
            #history = ['Searching' in mssg for mssg in self._sendMessages]
            if explanation in self._providedExplanations and mssg1 not in self._sendMessages[-5:]:
                self._sendMessage(mssg2,sender)   
        if 'Found' in mssg1:
            history = [mssg2[:-1] in mssg for mssg in self._sendMessages]
            if explanation in self._providedExplanations and True not in history:
                self._sendMessage(mssg2,sender)      
        if 'Searching' not in mssg1 and 'Found' not in mssg1:
            if explanation in self._providedExplanations and self._sendMessages[-1]!=mssg1:
                self._sendMessage(mssg2,sender) 