"""Shared local/sandbox interface. Never import student modules on the web host."""
import copy
import inspect
from .engine import STEER

class FunctionController:
    def __init__(self, function):
        inspect.signature(function).bind({}, {}, {}, None)
        self.function = function
        self.memory = None

    def act(self, observation):
        obs = copy.deepcopy(observation)
        reference = obs.pop('track')
        vehicle = {'length': 3.8, 'width': 1.6, 'wheelbase': 2.4,
                   'max_steering': STEER, 'dt': obs['dt']}
        steering, drive, memory = self.function(obs, reference, vehicle, self.memory)
        self.memory = memory
        return {'steering': steering, 'torque': drive}

def load_controller(module):
    if callable(getattr(module, 'control', None)):
        return FunctionController(module.control)
    # Historical submissions remain replayable/evaluable.
    return module.Controller()
