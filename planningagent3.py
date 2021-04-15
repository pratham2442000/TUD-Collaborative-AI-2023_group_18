from BW4TBrain import BW4TBrain
#from ColorBlindBW4TBrain import ColorBlindBW4TBrain
from BlockPositions import BlockPositions, sameAppearance
import enum
from matrx.agents.agent_utils.state import State
from matrx.agents.agent_utils.navigator import Navigator
from matrx.agents.agent_utils.state_tracker import StateTracker
from matrx.actions.door_actions import OpenDoorAction
from matrx.actions.object_actions import GrabObject, DropObject
import random
from matrx.messages.message import Message
import sys
import ast

class Phase(enum.Enum):
    PLAN_PATH_ALONG_DROPZONE=0, # to update our knowledge about placed blocks
    FOLLOW_PATH_ALONG_DROPZONE=1,
    FIND_NEXT_GOAL=2,# determine next goal zone
    PICK_SOME_CLOSED_DOOR=3, # we only explore closed rooms
    #we leave explored room doors open so we know we explored them
    #Pradeep decided we MUST enter room and search the inside
    PLAN_PATH_TO_CLOSED_DOOR=4,
    FOLLOW_PATH_TO_CLOSED_DOOR=5,
    OPEN_DOOR=6,
    PLAN_ROOM_SEARCH_PATH=7,
    FOLLOW_ROOM_SEARCH_PATH=8,
    PLAN_PATH_TO_BLOCK=9,
    FOLLOW_PATH_TO_BLOCK=10,
    TAKE_BLOCK=11,
    PLAN_PATH_TO_DROPPOINT=12,
    FOLLOW_PATH_TO_DROPPOINT=13,
    DROP_BLOCK=14
    
class BlockWorldAgent(BW4TBrain):
    """
    This extends planningagent2 with communication.
    """
    def __init__(self, slowdown:int):
        super().__init__(slowdown)
        self._phase=Phase.PLAN_PATH_ALONG_DROPZONE
        self._blockpositions = BlockPositions()

    #override
    def initialize(self):
        self._state_tracker = StateTracker(agent_id=self.agent_id)
        self._navigator = Navigator(agent_id=self.agent_id, 
            action_set=self.action_set, algorithm=Navigator.A_STAR_ALGORITHM)

    #override
    def filter_bw4t_observations(self, state):
        self._processMessages()
        return state

    #override
    def decide_on_bw4t_action(self, state:State):


        oldblocks=self._blockpositions
        self._blockpositions=self._blockpositions.update(state)

        changes=self._blockpositions.getDifference(oldblocks)
        #to_id=self._teamMembers(state) does not work ok yet
        #if len(changes)>0:
        #    msg = Message(content='Found:'+str(changes), 
        #        from_id='me' )
        #    self.send_message(msg)
        
            

        while True: 
            if Phase.PLAN_PATH_ALONG_DROPZONE==self._phase:
                self._navigator.reset_full()
                waypoints = map(lambda info:info['location'], self._getDropZones(state))
                self._navigator.add_waypoints(waypoints)
                self._phase = Phase.FOLLOW_PATH_ALONG_DROPZONE

            if Phase.FOLLOW_PATH_ALONG_DROPZONE==self._phase:
                # This explores the area so we know the needed blocks afterwards
                self._state_tracker.update(state)
                # execute the  path steps as planned in self._navigator
                action=self._navigator.get_move_action(self._state_tracker)
                if action!=None:
                    return action,{}
                # If we get here, we're there
                self._phase=Phase.FIND_NEXT_GOAL

            if Phase.FIND_NEXT_GOAL==self._phase:
                self._goalZone=None
                for info in self._getDropZones(state):
                    goodblocks = [blockinfo 
                        for blockinfo in self._blockpositions.getBlocksAt(info['location'])
                        if sameAppearance(blockinfo['img_name'], info['img_name'])]
                    if len(goodblocks)==0:
                        self._goalZone=info
                        break
                if self._goalZone==None:
                    # all blocks are in place. can't handle this situation.
                    self._phase=Phase.PLAN_PATH_ALONG_DROPZONE
                else:
                    # all known blocks with required appearance that are not in dropzone
                    options=self._blockpositions.getAppearance(self._goalZone['img_name'])
                    droplocs=[info['location'] for info in self._getDropZones(state)]
                    options=[info for info in options if not info['location'] in droplocs]
                    
                    if len(options)==0:
                        self._phase=Phase.PICK_SOME_CLOSED_DOOR
                    else:
                        self._block = random.choice(options)
                        self._phase=Phase.PLAN_PATH_TO_BLOCK
        
            if Phase.PICK_SOME_CLOSED_DOOR==self._phase:
                closedDoors=[door for door in state.values()
                    if 'class_inheritance' in door 
                    and 'Door' in door['class_inheritance']
                    and not door['is_open']]
                if len(closedDoors)==0:
                    # can't handle this situation. 
                    self._phase=Phase.PLAN_PATH_ALONG_DROPZONE
                else:
                    self._door=random.choice(closedDoors)
                    self._phase = Phase.PLAN_PATH_TO_CLOSED_DOOR
                    
            if Phase.PLAN_PATH_TO_CLOSED_DOOR == self._phase:
                # self._door must be set to target door
                self._navigator.reset_full()
                doorLoc:tuple = self._door['location']
                # HACK we assume door is at south side of room
                doorLoc = doorLoc[0],doorLoc[1]+1
                print("heading for door at ",doorLoc)
                self._navigator.add_waypoints([doorLoc])
                self._phase=Phase.FOLLOW_PATH_TO_CLOSED_DOOR
            
            if Phase.FOLLOW_PATH_TO_CLOSED_DOOR == self._phase:
                # self._door must be set
                self._state_tracker.update(state)
                # execute the  path steps as planned in self._navigator
                action=self._navigator.get_move_action(self._state_tracker)
                if action!=None:
                    return action,{}
                # If we get here, we're there
                self._phase=Phase.OPEN_DOOR

            if Phase.OPEN_DOOR==self._phase:
                # self._door must be set
                print("opening door!")
                self._phase=Phase.PLAN_ROOM_SEARCH_PATH
                return OpenDoorAction.__name__,{ 'object_id':self._door['obj_id']}

            if Phase.PLAN_ROOM_SEARCH_PATH==self._phase:
                # self._door must be set
                roomTiles = [info['location'] for info in state.values()
                    if 'class_inheritance' in info 
                    and 'AreaTile' in info['class_inheritance']
                    #notice, in matrx a room can go to only 1 door
                    # because of the 'room_name' property of doors
                    and 'room_name' in info
                    and info['room_name'] == self._door['room_name']
                ]
                # FIXME we want to sort these tiles for efficient search...
                # CHECK rooms don't need to be square I assume?
                self._navigator.reset_full()
                self._navigator.add_waypoints(roomTiles)
                self._phase=Phase.FOLLOW_ROOM_SEARCH_PATH
            
            if Phase.FOLLOW_ROOM_SEARCH_PATH == self._phase:
                self._state_tracker.update(state)
                action=self._navigator.get_move_action(self._state_tracker)
                if action!=None:
                    return action,{}
                # If we get here, we're done
                self._phase=Phase.FIND_NEXT_GOAL

            if Phase.PLAN_PATH_TO_BLOCK==self._phase:
                # self._block must be set to info of target block 
                # self._goalZone must be set to goalzone needing that block
                # we assume door to room containing block is open
                self._navigator.reset_full()
                self._navigator.add_waypoints([self._block['location']])
                self._phase=Phase.FOLLOW_PATH_TO_BLOCK
            
            if Phase.FOLLOW_PATH_TO_BLOCK == self._phase:
                # self._block must be set to info of target block 
                # self._goalZone must be set to goalzone needing that block
                self._state_tracker.update(state)
                action=self._navigator.get_move_action(self._state_tracker)
                if action!=None:
                    return action,{}
                if self._navigator.is_done:
                    self._phase=Phase.TAKE_BLOCK   
                else:
                    print("oops, door is closed?")
                    # door closed?? Explore that room now.
                    area = [area for area in state.values()
                          if 'class_inheritance' in area 
                          and 'AreaTile' in area['class_inheritance']
                          and area['location']==self._block['location']][0]
                    self._door=state.get_room_doors(area['room_name'])[0]
                    self._phase = Phase.PLAN_PATH_TO_CLOSED_DOOR

    
            if Phase.TAKE_BLOCK == self._phase:
                # self._block must be set to info of target block 
                # self._goalZone must be set to goalzone needing that block
                print("delivering block")
                msg = Message(content='Delivering '+str(self._block['img_name'])[8:-4], from_id='me' )
                self.send_message(msg)
                self._phase=Phase.PLAN_PATH_TO_DROPPOINT
                return GrabObject.__name__,{'object_id':self._block['obj_id']}
            
            if Phase.PLAN_PATH_TO_DROPPOINT==self._phase:
                # self._block must be set to info of target block 
                # self._goalZone must be set to goalzone needing that block
                self._navigator.reset_full()
                self._navigator.add_waypoints([self._goalZone['location']])
                self._phase=Phase.FOLLOW_PATH_TO_DROPPOINT

            if Phase.FOLLOW_PATH_TO_DROPPOINT==self._phase:
                self._state_tracker.update(state)
                # execute the  path steps as planned in self._navigator
                action=self._navigator.get_move_action(self._state_tracker)
                if action!=None:
                    return action,{}
                # If we get here, we're there
                self._phase=Phase.DROP_BLOCK
                
            if Phase.DROP_BLOCK == self._phase:
                print("Dropped box ",self._block)
                self._phase=Phase.FIND_NEXT_GOAL
                # don't use 'object_id':self._nextBlock[0],
                # there seems a bug in MATRX DropObject #7
                # Maybe it's fixed now
                return DropObject.__name__,{}
    
    def _getDropZones(self,state:State):
        '''
        @return list of drop zones (their full dict), in order (the first one is the
        the place that requires the first drop)
        '''
        # we must use is_goal_block, not is_drop_zone, to collect also the
        # correct appearance
        places=state[{'is_goal_block':True}]
        # sort does in-place sorting
        places.sort(key=lambda info:info['location'][1], reverse=True)
        return places
    
    def _isCarrying(self, state:State,appearance:dict):
        """
        @param state the current State
        @param appearance a dict with the required block appearance
        @return true iff we are carrying a block of given appearance
        """
        for carrying in state[self.agent_id]['is_carrying']:
            if sameAppearance(carrying['img_name'], appearance):
                return True
        return False
        

    def _getDropOff(self, state:State,y:int)-> tuple:
        """
        @param y the y location of the required drop off location
        @return the drop off location (x,y) given the y.
        @throws out of index error if there is no drop zone at given y position.
        """
        for id in state.keys():
            if 'is_drop_zone' in state[id] and state[id]['location'][1] == y:
                return state[id]['location']
        raise ValueError("There is no block at y location "+str(y))
        

    def _findLocationOfBlock(self, state:State,appearance:dict):
        """
        @param state the current State
        @param appearance the 'visualization' settings. Must contain
        'size', 'shape' and  color.
        @return (id, x,y) of a block of requested appearance,
        that is not already on a dropoff point or being carried.
        """
        droplocations=[state[id]['location'] 
           for id in state.keys() 
           if 'is_goal_block' in state[id] and state[id]['is_goal_block']]

        # find locations of all blocks of given appearance that are not already
        # on a droplocation
        locs=[(id,)+state[id]['location'] for id in state.keys() 
            if 'is_collectable' in state[id] 
            and state[id]['is_collectable'] 
            and state[id]['img_name']==appearance['img_name']
            #and state[id]['visualization']['size']==appearance['size']
            #and state[id]['visualization']['shape']==appearance['shape']
            #and state[id]['visualization']['colour']==appearance['colour']
            and not state[id]['location'] in droplocations
            and len(state[id]['carried_by'])==0
            ]
        if len(locs)==0:
            return None
        return random.choice(locs)

    def _findRoomContaining(self, state:State, loc:tuple):
        """
        @param loc the (x,y) location 
        @return a (should be unique) room name 
        that contains that location, or None if no such room.
        Basically we look for an AreaTile at given loc. 
        NOTICE: room name is a label used by the room designer,
        it's not the ID. I assume that properly designed 
        worlds use this label consistently to tag other objects in the same room,
        typically the doors tiles and walls.
        """
        locs=[state[id]['room_name'] for id in state.keys() 
            if 'class_inheritance' in state[id]
            and 'AreaTile' in state[id]['class_inheritance']
            and state[id]['location'] == loc
        ]
        if (len(locs)==0):
            return None
        return locs[0]

    def _processMessages(self):
        '''
        process incoming messages. 
        Reported blocks are added to self._blocks
        '''
        if len(self.received_messages)>0:
            print(self.agent_name+" recvd msgs:",self.received_messages )
        for msg in self.received_messages:
            if msg.startswith("Found:"):
                try:
                    content=msg[6:]
                    infos=ast.literal_eval(content)
                    for blockinfo in infos:
                        self._blockpositions = self._blockpositions.updateInfo(blockinfo)
                except:
                    print("Warning. parsing err "+str(sys.exc_info())+": "+content)
        #workaround for bug
        self.received_messages=[]

    def _teamMembers(self, state):
        '''
        @param state the State
        @return team members, except me
        '''
        #Due to bug #241 this does not work properly now.
        return [info['name'] for info in state.values()
                if 'isAgent' in info 
                and info['name']!=self.agent_name]
    