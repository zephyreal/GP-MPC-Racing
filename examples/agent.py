"""Student entry. Replace Controller.act using the documented observation/action protocol."""
from gp_mpc_racing.controllers import PursuitController
class Controller(PursuitController):
    def __init__(self):super().__init__(speed=8.,lookahead=7.)
