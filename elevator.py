import os, time
from enum import Enum

ELEVATOR_COUNT = 2
MAX_FLOOR = 7
REQUEST_PIPE = "/tmp/elevator_request_queue"
WAIT_TIME = 5
# Message format is [floor, "up"/"down"]

# debug variable
total_rounds = 0

total_num_rounds_to_pick_up_request = 0
total_picked_up_requests = 0

class Direction(Enum):
    Up = 1
    Down = 2
    Idle = 3

class Request:
    def __init__(self, _floor, _direction, _target):
        self.floor = _floor
        self.direction = _direction
        self.target = _target

        # debug variable
        self.request_issued_time_in_round = total_rounds

class Elevator:
    # default constructor
    def __init__(self):
        self.direction = Direction.Idle
        self.floor = 1
        self.target = None
    
    def handle(self, request: Request):
        # debug variables
        global total_picked_up_requests
        global total_num_rounds_to_pick_up_request

        if self.direction == Direction.Idle:
            # we need to know whether we are:
            #   1. going to get a request cuz we are idle 
            #   2. getting a request when we are idle
            target_floor = request.floor if (self.floor != request.floor) else request.target
            self.target = target_floor
            if (target_floor - self.floor) > 0:
                self.direction = Direction.Up
            elif (target_floor - self.floor) < 0:
                self.direction = Direction.Down
            else:
                self.direction = Direction.Idle

        elif self.direction == Direction.Down:
            if (self.target > request.target):
                self.target = request.target
        elif self.direction == Direction.Up:
            if (self.target < request.target):
                self.target = request.target

        # calculate number of rounds this request spend waiting
        if(self.floor == request.floor):
            total_picked_up_requests += 1
            total_num_rounds_to_pick_up_request += (total_rounds - request.request_issued_time_in_round)

    def move_once(self):
        if(self.direction == Direction.Up):
            self.floor += 1
        if(self.direction == Direction.Down):
            self.floor -= 1
        if(self.floor == self.target):
            self.target = None
            self.direction = Direction.Idle


def elevator_can_pick_up_request(elevator: Elevator,
                                request: Request):
    
    if (elevator.target== request.floor):
        return True
    if ((elevator.floor - request.floor) > 0 and elevator.direction == Direction.Down):
        if request.direction == Direction.Down and elevator.target < request.floor:
            return True
    if ((elevator.floor - request.floor) < 0 and elevator.direction == Direction.Up):
        if request.direction == Direction.Up and elevator.target > request.floor:
            return True
    return False

def handle_request(request:Request,
                   elevator_list,
                   floor_request_map):

    if request.floor > MAX_FLOOR or request.direction == Direction.Idle:
        return
    floor_request_map[request.floor][request.direction] = (request, False)
    
    # prioritize elevators that can pick up request along the way
    for elevator in elevator_list:
        if(elevator_can_pick_up_request(elevator, request)):
            # since some elevator can pick up the request, we don't worry about handling it
            floor_request_map[request.floor][request.direction] = (request, True)
            return
    
    handler = None
    distance = MAX_FLOOR + 1
    for elevator in elevator_list:
        if(elevator.direction == Direction.Idle and abs(elevator.floor - request.floor) < distance):
            distance = abs(elevator.floor - request.floor)
            handler = elevator

    handler.handle(request)
    floor_request_map[request.floor][request.direction] = (request, True)
    
    # if there are no elevators that can pick up the request,
    # and no elevators that is idle, we handle the request next time
    
def parse_request(message: str):
    token = message.strip().split(',')
    floor = token[0]
    target = token[2]
    direction = Direction.Idle
    print(token)
    if token[1] == "up":
        direction = Direction.Up
    elif token[1] == "down":
        direction = Direction.Down
    return Request(int(floor), direction, int(target))
    
def main():
    global total_rounds

    elevator_list = []
    floor_request_map = {}
    
    for i in range(ELEVATOR_COUNT):
        elevator_list.append(Elevator())
    
    for i in range(MAX_FLOOR + 1):
        floor_request_map[i] = dict()    
        floor_request_map[i][Direction.Up] = None
        floor_request_map[i][Direction.Down] = None
    
    # set up request pipe
    if not os.path.exists(REQUEST_PIPE):
        os.mkfifo(REQUEST_PIPE)
    pipe_fd = os.open(REQUEST_PIPE, os.O_RDONLY | os.O_NONBLOCK)

    with os.fdopen(pipe_fd) as pipe:
        while True:
            total_rounds += 1
            # Every elevator try to pick up a request along the way
            for elevator in elevator_list:
                cur_floor = elevator.floor
                if(elevator.direction == Direction.Idle):
                    # this case we can pick up any request
                    if(floor_request_map[cur_floor][Direction.Down]):
                        elevator.handle(floor_request_map[cur_floor][Direction.Down][0])
                        floor_request_map[cur_floor][Direction.Down] = None
                    elif(floor_request_map[cur_floor][Direction.Up]):
                        elevator.handle(floor_request_map[cur_floor][Direction.Up][0])
                        floor_request_map[cur_floor][Direction.Up] = None
                elif(elevator.direction == Direction.Up):
                    # if moving up, only pick up requests going up
                    if(floor_request_map[cur_floor][Direction.Up]):
                        elevator.handle(floor_request_map[cur_floor][Direction.Up][0])
                        floor_request_map[cur_floor][Direction.Up] = None
                elif(elevator.direction == Direction.Down):
                    # if moving down, only pick up requests going down
                    if(floor_request_map[cur_floor][Direction.Down]):
                        elevator.handle(floor_request_map[cur_floor][Direction.Down][0])
                        floor_request_map[cur_floor][Direction.Down] = None

            # Go through all the unhandled requests, handle them if there is an idle elevator
            for i in range(MAX_FLOOR):
                if (floor_request_map[i][Direction.Up] and 
                   not floor_request_map[i][Direction.Up][1]):
                   handle_request(floor_request_map[i][Direction.Up][0],
                                    elevator_list,
                                    floor_request_map)
                if (floor_request_map[i][Direction.Down] and 
                   not floor_request_map[i][Direction.Down][1]):
                   handle_request(floor_request_map[i][Direction.Down][0],
                                    elevator_list,
                                    floor_request_map)
            
            # listen for a new request
            message = pipe.read()
            if message:
                print("Received: '%s'" % message)
                # algorithm for handling request
                request = parse_request(message)
                handle_request(request, elevator_list, floor_request_map)

            # every elevator move once
            for elevator in elevator_list:
                elevator.move_once()

            print("Elevator states:")
            for i, elevator in enumerate(elevator_list):
                print("Elevator " + str(i) + " is on floor " + str(elevator.floor))
            
            print("System staticstics:")
            if total_picked_up_requests > 0:
                print(f"Average request waiting time in rounds: {total_num_rounds_to_pick_up_request / total_picked_up_requests}")
            else:
                print(f"Average request waiting time in rounds: 0")
            
            time.sleep(WAIT_TIME)
        
if __name__ == "__main__":
    main()