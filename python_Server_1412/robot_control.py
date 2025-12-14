from dobot_api import DobotApiDashboard, DobotApiMove, DobotApi
from calibration_affine import pixel_to_robot
import time
import math


class RobotController:
    def __init__(self):
        self.client_dash = None
        self.client_move = None
        self.client_feed = None
        self.connected = False

    # ----------------------------------------------------------------------
    def connect(self, ip):
        try:
            self.client_dash = DobotApiDashboard(ip, 29999)
            self.client_move = DobotApiMove(ip, 30003)
            self.client_feed = DobotApi(ip, 30004)

            self.client_dash.SpeedFactor(30)
            self.connected = True

            return True, "Connected"
        except Exception as e:
            self.connected = False
            return False, str(e)

    # ----------------------------------------------------------------------
    def enable_robot(self, enable):
        if not self.connected:
            return {"status": "error", "message": "Not connected"}

        try:
            if enable:
                self.client_dash.EnableRobot()
            else:
                self.client_dash.DisableRobot()
            return {"status": "success"}
        except Exception as e:
            return {"status": "error", "message": str(e)}

    # ----------------------------------------------------------------------
    def reset_robot(self):
        if not self.connected:
            return {"status": "error", "message": "Not connected"}
        self.client_dash.ResetRobot()
        return {"status": "success"}

    # ----------------------------------------------------------------------
    def clear_error(self):
        if not self.connected:
            return {"status": "error", "message": "Not connected"}
        self.client_dash.ClearError()
        return {"status": "success"}

    # ----------------------------------------------------------------------
    def emergency_stop(self):
        if not self.connected:
            return {"status": "error", "message": "Not connected"}
        self.client_dash.EmergencyStop()
        return {"status": "success"}

    # ----------------------------------------------------------------------
    def move(self, data):
        if not self.connected:
            return {"status": "error", "message": "Not connected"}

        try:
            mode = data.get("mode")
            if mode == "MovJ":
                self.client_move.MovJ(data["x"], data["y"], data["z"], data["r"])

            elif mode == "MovL":
                self.client_move.MovL(data["x"], data["y"], data["z"], data["r"])

            elif mode == "home":
                self.client_move.JointMovJ(0, 0, 0, 200)

            return {"status": "success"}

        except Exception as e:
            return {"status": "error", "message": str(e)}

    # ----------------------------------------------------------------------
    def click_to_pick(self, pos, visible_tags):
        if not self.connected:
            return {"status": "error", "message": "Robot not connected"}

        click_x = pos.get("x")
        click_y = pos.get("y")

        nearest = None
        best_dist = 50.0

        for t in visible_tags:
            d = math.dist((click_x, click_y), (t["cx"], t["cy"]))
            if d < best_dist:
                best_dist = d
                nearest = t

        if not nearest:
            return {"status": "error", "message": "No tag near click"}

        if not nearest["zone"]:
            return {"status": "error", "message": "Tag not in any safe zone"}

        rx, ry = pixel_to_robot(nearest["cx"], nearest["cy"])
        z = nearest["zone"]["z"]

        try:
            self.client_move.MovJ(rx, ry, 50, 0)
            # self.client_move.MovL(rx, ry, z, 0)

            return {
                "status": "success",
                "target": {"x": rx, "y": ry}
            }

        except Exception as e:
            return {"status": "error", "message": str(e)}
