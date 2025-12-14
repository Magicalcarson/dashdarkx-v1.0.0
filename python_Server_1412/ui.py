# -*- coding: utf-8 -*-
from threading import Thread
import time
from tkinter import *
from tkinter import ttk, messagebox
from tkinter.scrolledtext import ScrolledText
from dobot_api import *
import json

# --- ปิด Import ไฟล์ Alarm เพื่อกัน Crash (ถ้ามีไฟล์ files/ ค่อยเปิดบรรทัดนี้) ---
# from files.alarm_controller import alarm_controller_list
# from files.alarm_servo import alarm_servo_list

LABEL_JOINT = [["J1-", "J2-", "J3-", "J4-"],
               ["J1:", "J2:", "J3:", "J4:"],
               ["J1+", "J2+", "J3+", "J4+"]]

LABEL_COORD = [["X-", "Y-", "Z-", "R-"],
               ["X:", "Y:", "Z:", "R"],
               ["X+", "Y+", "Z+", "R+"]]

LABEL_ROBOT_MODE = {
    1:  "ROBOT_MODE_INIT",
    2:  "ROBOT_MODE_BRAKE_OPEN",
    3:  "",
    4:  "ROBOT_MODE_DISABLED",
    5:  "ROBOT_MODE_ENABLE",
    6:  "ROBOT_MODE_BACKDRIVE",
    7:  "ROBOT_MODE_RUNNING",
    8:  "ROBOT_MODE_RECORDING",
    9:  "ROBOT_MODE_ERROR",
    10: "ROBOT_MODE_PAUSE",
    11: "ROBOT_MODE_JOG"
}


class RobotUI(object):

    def __init__(self):
        self.root = Tk()
        self.root.title("Dobot MG400 (Safety Speed 30%)")
        self.root.geometry("930x850")
        self.root.configure(bg="#F0F2F5") 

        self.root.protocol("WM_DELETE_WINDOW", self.on_closing)

        self.global_state = {}
        self.button_list = []
        self.entry_dict = {}

        # --- 1. Robot Connect ---
        self.frame_robot = LabelFrame(self.root, text="Robot Connect",
                                      labelanchor="nw", bg="#FFFFFF", width=870, height=120, border=2)

        self.label_ip = Label(self.frame_robot, text="IP Address:", bg="#FFFFFF")
        self.label_ip.place(rely=0.2, x=10)
        
        ip_port = StringVar(self.root, value="192.168.1.6") 
        self.entry_ip = Entry(self.frame_robot, width=12, textvariable=ip_port)
        self.entry_ip.place(rely=0.2, x=90)

        self.label_dash = Label(self.frame_robot, text="Dashboard Port:", bg="#FFFFFF")
        self.label_dash.place(rely=0.2, x=210)
        dash_port = IntVar(self.root, value=29999)
        self.entry_dash = Entry(self.frame_robot, width=7, textvariable=dash_port)
        self.entry_dash.place(rely=0.2, x=320)

        self.label_move = Label(self.frame_robot, text="Move Port:", bg="#FFFFFF")
        self.label_move.place(rely=0.2, x=400)
        move_port = IntVar(self.root, value=30003)
        self.entry_move = Entry(self.frame_robot, width=7, textvariable=move_port)
        self.entry_move.place(rely=0.2, x=480)

        self.label_feed = Label(self.frame_robot, text="Feedback Port:", bg="#FFFFFF")
        self.label_feed.place(rely=0.2, x=580)
        feed_port = IntVar(self.root, value=30004)
        self.entry_feed = Entry(self.frame_robot, width=7, textvariable=feed_port)
        self.entry_feed.place(rely=0.2, x=680)

        self.button_connect = self.set_button(master=self.frame_robot,
                                              text="Connect", rely=0.6, x=630, command=self.connect_port,
                                              bg="#007bff", fg="white", font=("Arial", 10, "bold"))
        self.button_connect["width"] = 10
        self.global_state["connect"] = False

        # --- 2. Dashboard Function ---
        self.frame_dashboard = LabelFrame(self.root, text="Dashboard Function",
                                          labelanchor="nw", bg="#FFFFFF", pady=10, width=870, height=120, border=2)

        self.button_enable = self.set_button(master=self.frame_dashboard,
                                             text="Enable", rely=0.1, x=10, command=self.enable,
                                             bg="#28a745", fg="white", font=("Arial", 10, "bold"))
        self.button_enable["width"] = 7
        self.global_state["enable"] = False

        self.set_button(master=self.frame_dashboard,
                        text="Reset Robot", rely=0.1, x=145, command=self.reset_robot, bg="#ffc107")
        
        self.set_button(master=self.frame_dashboard,
                        text="Clear All Errors", rely=0.1, x=290, command=self.clear_all_errors, bg="#ffc107")

        self.label_speed = Label(self.frame_dashboard, text="Speed Ratio:", bg="#FFFFFF")
        self.label_speed.place(rely=0.1, x=430)

        # >>>> SAFETY SPEED LIMIT 30% DEFAULT <<<<
        s_value = StringVar(self.root, value="30")
        self.entry_speed = Entry(self.frame_dashboard, width=6, textvariable=s_value)
        self.entry_speed.place(rely=0.1, x=520)
        self.label_cent = Label(self.frame_dashboard, text="%", bg="#FFFFFF")
        self.label_cent.place(rely=0.1, x=550)

        self.set_button(master=self.frame_dashboard,
                        text="Confirm", rely=0.1, x=586, command=self.confirm_speed)

        self.label_digitial = Label(self.frame_dashboard, text="Digital Outputs: Index:", bg="#FFFFFF")
        self.label_digitial.place(rely=0.55, x=10)
        i_value = IntVar(self.root, value="1")
        self.entry_index = Entry(self.frame_dashboard, width=5, textvariable=i_value)
        self.entry_index.place(rely=0.55, x=160)

        self.label_status = Label(self.frame_dashboard, text="Status:", bg="#FFFFFF")
        self.label_status.place(rely=0.55, x=220)
        self.combo_status = ttk.Combobox(self.frame_dashboard, width=5)
        self.combo_status["value"] = ("On", "Off")
        self.combo_status.current(0)
        self.combo_status["state"] = "readonly"
        self.combo_status.place(rely=0.55, x=275)

        self.set_button(self.frame_dashboard, "Confirm", rely=0.55, x=350, command=self.confirm_do)

        # --- 3. Move Function ---
        self.frame_move = LabelFrame(self.root, text="Move Function", labelanchor="nw",
                                     bg="#FFFFFF", width=870, pady=10, height=130, border=2)

        self.set_move(text="X:", label_value=10, default_value="600", entry_value=40, rely=0.1, master=self.frame_move)
        self.set_move(text="Y:", label_value=110, default_value="-260", entry_value=140, rely=0.1, master=self.frame_move)
        self.set_move(text="Z:", label_value=210, default_value="380", entry_value=240, rely=0.1, master=self.frame_move)
        self.set_move(text="R:", label_value=310, default_value="170", entry_value=340, rely=0.1, master=self.frame_move)

        self.set_button(master=self.frame_move, text="MovJ", rely=0.05, x=410, command=self.movj)
        self.set_button(master=self.frame_move, text="MovL", rely=0.05, x=500, command=self.movl)
        
        # >>>> GO HOME BUTTON (สีแดง) <<<<
        self.set_button(master=self.frame_move, text="GO HOME",
                        rely=0.05, x=600, command=self.go_home,
                        bg="#dc3545", fg="white", font=("Arial", 11, "bold"))

        self.set_move(text="J1:", label_value=10, default_value="0", entry_value=40, rely=0.5, master=self.frame_move)
        self.set_move(text="J2:", label_value=110, default_value="-20", entry_value=140, rely=0.5, master=self.frame_move)
        self.set_move(text="J3:", label_value=210, default_value="-80", entry_value=240, rely=0.5, master=self.frame_move)
        self.set_move(text="J4:", label_value=310, default_value="30", entry_value=340, rely=0.5, master=self.frame_move)

        self.set_button(master=self.frame_move, text="JointMovJ", rely=0.45, x=410, command=self.joint_movj)

        # --- 4. Feedback & Log ---
        self.frame_feed_log = Frame(self.root, bg="#FFFFFF", width=870, pady=10, height=400, border=2)
        
        self.frame_feed = LabelFrame(self.frame_feed_log, text="Feedback", labelanchor="nw",
                                     bg="#FFFFFF", width=550, height=150)
        self.frame_feed.place(relx=0, rely=0, relheight=1)

        self.set_label(self.frame_feed, text="Current Speed Ratio:", rely=0.05, x=10)
        self.label_feed_speed = self.set_label(self.frame_feed, "", rely=0.05, x=145)
        self.set_label(self.frame_feed, text="%", rely=0.05, x=175)

        self.set_label(self.frame_feed, text="Robot Mode:", rely=0.1, x=10)
        self.label_robot_mode = self.set_label(self.frame_feed, "", rely=0.1, x=95)

        self.label_feed_dict = {}
        self.set_feed(LABEL_JOINT, 9, 52, 74, 117)
        self.set_feed(LABEL_COORD, 165, 209, 231, 272)

        self.set_label(self.frame_feed, "Digital Inputs:", rely=0.8, x=11)
        self.label_di_input = self.set_label(self.frame_feed, "", rely=0.8, x=100)
        self.set_label(self.frame_feed, "Digital Outputs:", rely=0.85, x=10)
        self.label_di_output = self.set_label(self.frame_feed, "", rely=0.85, x=100)

        self.frame_err = LabelFrame(self.frame_feed, text="Error Info", labelanchor="nw",
                                    bg="#FFFFFF", width=180, height=50)
        self.frame_err.place(relx=0.65, rely=0, relheight=0.7)

        self.text_err = ScrolledText(self.frame_err, width=170, height=50, relief="flat")
        self.text_err.place(rely=0, relx=0, relheight=0.7, relwidth=1)

        self.set_button(self.frame_feed, "Clear", rely=0.71, x=487, command=self.clear_text_only)

        self.frame_log = LabelFrame(self.frame_feed_log, text="Log", labelanchor="nw",
                                    bg="#FFFFFF", width=300, height=150)
        self.frame_log.place(relx=0.65, rely=0, relheight=1)

        self.text_log = ScrolledText(self.frame_log, width=270, height=140, relief="flat")
        self.text_log.place(rely=0, relx=0, relheight=1, relwidth=1)

        self.client_dash = None
        self.client_move = None
        self.client_feed = None

        self.alarm_controller_dict = {}
        self.alarm_servo_dict = {} 

    # >>>> FUNCTION: GO HOME (J1=0, J2=0, J3=0, J4=300) <<<<
    def go_home(self):
        if self.global_state.get("connect", False):
            print("Moving to HOME (J1=0, J2=0, J3=0, J4=300)...")
            self.client_move.JointMovJ(0.0, 0.0, 0.0, 300.0) 
        else:
            messagebox.showwarning("Alert", "Please Connect first!")

    def clear_all_errors(self):
        if self.global_state.get("connect", False):
            self.client_dash.ClearError()
        self.text_err.delete("1.0", "end")
        self.text_log.delete("1.0", "end")
        print("All errors & logs cleared.")

    def clear_text_only(self):
        self.text_err.delete("1.0", "end")

    def on_closing(self):
        if messagebox.askokcancel("Quit", "Do you want to quit?"):
            try:
                self.text_err.delete("1.0", "end")
                self.text_log.delete("1.0", "end")
            except: pass

            self.global_state["connect"] = False
            try:
                if self.client_dash: self.client_dash.close()
                if self.client_feed: self.client_feed.close()
                if self.client_move: self.client_move.close()
            except: pass
            
            self.root.quit()
            self.root.destroy()

    def convert_dict(self, alarm_list):
        return {} 

    def read_file(self, path):
        return {} 

    def mainloop(self):
        self.root.mainloop()

    def pack(self):
        self.frame_robot.pack()
        self.frame_dashboard.pack()
        self.frame_move.pack()
        self.frame_feed_log.pack()

    def set_move(self, text, label_value, default_value, entry_value, rely, master):
        self.label = Label(master, text=text, bg="#FFFFFF")
        self.label.place(rely=rely, x=label_value)
        value = StringVar(self.root, value=default_value)
        self.entry_temp = Entry(master, width=6, textvariable=value)
        self.entry_temp.place(rely=rely, x=entry_value)
        self.entry_dict[text] = self.entry_temp

    def move_jog(self, text):
        if self.global_state["connect"]:
            self.client_move.MoveJog(text)

    def move_stop(self, event):
        if self.global_state["connect"]:
            self.client_move.MoveJog("")

    def set_button(self, master, text, rely, x, **kargs):
        cmd = kargs.pop("command", None)
        self.button = Button(master, text=text, padx=5, command=cmd, **kargs)
        self.button.place(rely=rely, x=x)

        if text != "Connect":
            self.button["state"] = "disable"
            self.button_list.append(self.button)
        return self.button

    def set_button_bind(self, master, text, rely, x, **kargs):
        self.button = Button(master, text=text, padx=5)
        self.button.bind("<ButtonPress-1>", lambda event: self.move_jog(text=text))
        self.button.bind("<ButtonRelease-1>", self.move_stop)
        self.button.place(rely=rely, x=x)

        if text != "Connect":
            self.button["state"] = "disable"
            self.button_list.append(self.button)
        return self.button

    def set_label(self, master, text, rely, x):
        self.label = Label(master, text=text, bg="#FFFFFF")
        self.label.place(rely=rely, x=x)
        return self.label

    def connect_port(self):
        if self.global_state["connect"]:
            print("Disconnect success")
            self.global_state["connect"] = False
            try:
                self.client_dash.close()
                self.client_feed.close()
                self.client_move.close()
            except: pass
            
            self.client_dash = None
            self.client_feed = None
            self.client_move = None

            for i in self.button_list:
                i["state"] = "disable"
            self.button_connect["text"] = "Connect"
            self.button_connect.configure(bg="#007bff")
        else:
            try:
                print("Connect success")
                self.client_dash = DobotApiDashboard(
                    self.entry_ip.get(), int(self.entry_dash.get()), self.text_log)
                self.client_move = DobotApiMove(
                    self.entry_ip.get(), int(self.entry_move.get()), self.text_log)
                self.client_feed = DobotApi(
                    self.entry_ip.get(), int(self.entry_feed.get()), self.text_log)
                
                # >>>> FORCE SAFETY SPEED 30% ON CONNECT <<<<
                self.client_dash.SpeedFactor(30)
                self.text_log.insert(END, "Safety Speed set to 30%.\n")
                
            except Exception as e:
                messagebox.showerror("Attention!", f"Connection Error:{e}")
                return

            for i in self.button_list:
                i["state"] = "normal"
            self.button_connect["text"] = "Disconnect"
            self.button_connect.configure(bg="#dc3545")
            self.global_state["connect"] = True
            self.set_feed_back()

    def set_feed_back(self):
        if self.global_state["connect"]:
            thread = Thread(target=self.feed_back)
            thread.setDaemon(True)
            thread.start()

    def enable(self):
        if self.global_state["enable"]:
            self.client_dash.DisableRobot()
            self.button_enable["text"] = "Enable"
            self.button_enable.configure(bg="#28a745")
        else:
            self.client_dash.EnableRobot()
            self.button_enable["text"] = "Disable"
            self.button_enable.configure(bg="#dc3545")

        self.global_state["enable"] = not self.global_state["enable"]

    def reset_robot(self):
        self.client_dash.ResetRobot()

    def clear_error(self):
        self.client_dash.ClearError()

    def confirm_speed(self):
        self.client_dash.SpeedFactor(int(self.entry_speed.get()))

    def movj(self):
        self.client_move.MovJ(float(self.entry_dict["X:"].get()), float(self.entry_dict["Y:"].get()), float(self.entry_dict["Z:"].get()),
                              float(self.entry_dict["R:"].get()))

    def movl(self):
        self.client_move.MovL(float(self.entry_dict["X:"].get()), float(self.entry_dict["Y:"].get()), float(self.entry_dict["Z:"].get()),
                              float(self.entry_dict["R:"].get()))

    def joint_movj(self):
        self.client_move.JointMovJ(float(self.entry_dict["J1:"].get()), float(self.entry_dict["J2:"].get()), float(self.entry_dict["J3:"].get()),
                                   float(self.entry_dict["J4:"].get()))

    def confirm_do(self):
        if self.combo_status.get() == "On":
            print("High Level")
            self.client_dash.DO(int(self.entry_index.get()), 1)
        else:
            print("Low Level")
            self.client_dash.DO(int(self.entry_index.get()), 0)

    def set_feed(self, text_list, x1, x2, x3, x4):
        self.set_button_bind(
            self.frame_feed, text_list[0][0], rely=0.2, x=x1, command=lambda: self.move_jog(text_list[0][0]))
        self.set_button_bind(
            self.frame_feed, text_list[0][1], rely=0.3, x=x1, command=lambda: self.move_jog(text_list[0][1]))
        self.set_button_bind(
            self.frame_feed, text_list[0][2], rely=0.4, x=x1, command=lambda: self.move_jog(text_list[0][2]))
        self.set_button_bind(
            self.frame_feed, text_list[0][3], rely=0.5, x=x1, command=lambda: self.move_jog(text_list[0][3]))

        self.set_label(self.frame_feed, text_list[1][0], rely=0.21, x=x2)
        self.set_label(self.frame_feed, text_list[1][1], rely=0.31, x=x2)
        self.set_label(self.frame_feed, text_list[1][2], rely=0.41, x=x2)
        self.set_label(self.frame_feed, text_list[1][3], rely=0.51, x=x2)

        self.label_feed_dict[text_list[1][0]] = self.set_label(
            self.frame_feed, " ", rely=0.21, x=x3)
        self.label_feed_dict[text_list[1][1]] = self.set_label(
            self.frame_feed, " ", rely=0.31, x=x3)
        self.label_feed_dict[text_list[1][2]] = self.set_label(
            self.frame_feed, " ", rely=0.41, x=x3)
        self.label_feed_dict[text_list[1][3]] = self.set_label(
            self.frame_feed, " ", rely=0.51, x=x3)

        self.set_button_bind(
            self.frame_feed, text_list[2][0], rely=0.2, x=x4, command=lambda: self.move_jog(text_list[2][0]))
        self.set_button_bind(
            self.frame_feed, text_list[2][1], rely=0.3, x=x4, command=lambda: self.move_jog(text_list[2][1]))
        self.set_button_bind(
            self.frame_feed, text_list[2][2], rely=0.4, x=x4, command=lambda: self.move_jog(text_list[2][2]))
        self.set_button_bind(
            self.frame_feed, text_list[2][3], rely=0.5, x=x4, command=lambda: self.move_jog(text_list[2][3]))

    def feed_back(self):
        hasRead = 0
        while True:
            if not self.global_state["connect"]:
                break
            data = bytes()
            while hasRead < 1440:
                try:
                    temp = self.client_feed.socket_dobot.recv(1440 - hasRead)
                    if len(temp) > 0:
                        hasRead += len(temp)
                        data += temp
                    else: break
                except: break
            
            if len(data) < 1440: continue
            hasRead = 0

            a = np.frombuffer(data, dtype=MyType)
            if hex((a['test_value'][0])) == '0x123456789abcdef':
                try:
                    self.label_feed_speed["text"] = a["speed_scaling"][0]
                    self.label_robot_mode["text"] = LABEL_ROBOT_MODE[a["robot_mode"][0]]
                    self.label_di_input["text"] = bin(a["digital_input_bits"][0])[
                        2:].rjust(64, '0')
                    self.label_di_output["text"] = bin(a["digital_outputs"][0])[
                        2:].rjust(64, '0')

                    self.set_feed_joint(LABEL_JOINT, a["q_actual"])
                    self.set_feed_joint(LABEL_COORD, a["tool_vector_actual"])

                    if a["robot_mode"] == 9:
                        self.display_error_info()
                except: pass

            time.sleep(0.005)

    def display_error_info(self):
        pass

    def form_error(self, index, alarm_dict: dict, type_text):
        pass

    def clear_error_info(self):
        self.text_err.delete("1.0", "end")

    def set_feed_joint(self, label, value):
        array_value = np.around(value, decimals=4)
        self.label_feed_dict[label[1][0]]["text"] = array_value[0][0]
        self.label_feed_dict[label[1][1]]["text"] = array_value[0][1]
        self.label_feed_dict[label[1][2]]["text"] = array_value[0][2]
        self.label_feed_dict[label[1][3]]["text"] = array_value[0][3]