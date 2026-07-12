#!/usr/bin/env python
# -*- coding: utf-8 -*-

########################################################
# This file have all the functions of the RMD V1
########################################################

from .rmd_dcl import *
from .can_handler import *
import can


class RMD1(RMD_dcl, CAN_Handler):
    def __init__(self, bustype="socketcan", channel="can0", bitrate=1000000):
        CAN_Handler.__init__(self, bustype, channel, bitrate)
        self.bus = can.interface.Bus(bustype=bustype, channel=channel, bitrate=bitrate)

    # Read PID parameter command 0x30
    def RD_PID_Data(self):
        data = [0x30, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00]
        return data

    # Write PID parameter to RAM command 0x31
    def WR_PID_RAM(self, PositionKP, PositionKi, SpeedKp, SpeedKi, TorqueKp, TorqueKi):
        data = [
            0x31,
            0x00,
            PositionKP,
            PositionKi,
            SpeedKp,
            SpeedKi,
            TorqueKp,
            TorqueKi,
        ]
        return data

    # Write PID parameter to ROM command 0x32
    def WR_PID_ROM(self, PositionKP, PositionKi, SpeedKp, SpeedKi, TorqueKp, TorqueKi):
        data = [
            0x32,
            0x00,
            PositionKP,
            PositionKi,
            SpeedKp,
            SpeedKi,
            TorqueKp,
            TorqueKi,
        ]
        return data

    # Read acceleration data command 0x33
    def RD_Acceleration_Data(self):
        data = [0x33, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00]
        return data

    # Write acceleration data to RAM command 0x34
    def WR_Acceleration_Data(self, Acceleration):
        Acceleration = bytearray.fromhex(
            f"{(Signed_int_to_hex(int(Acceleration*6), 32)[2:]):0>8}"
        )
        data = [
            0x34,
            0x00,
            0x00,
            0x00,
            Acceleration[3],
            Acceleration[2],
            Acceleration[1],
            Acceleration[0],
        ]
        return data

    # Read encoder data command 0x90
    def RD_Encoder_Data(self):
        data = [0x90, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00]
        return data

    # Write Encoder Position Command 0x91
    def WR_Encoder_Offset(self, Offset):
        Offset = bytearray.fromhex(f"{(hex(int(Offset))[2:]):0>4}")
        data = [0x91, 0x00, 0x00, 0x00, 0x00, 0x00, Offset[1], Offset[0]]
        return data

    # Write current position to ROM as motor zero position command 0x19
    def WR_Current_Position_AS_Offset_ROM(self):
        data = [0x19, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00]
        return data

    # Read multi turns angle command 0x92
    def RD_Multi_turn_Angle(self):
        data = [0x92, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00]
        return data

    # Read single circle angle command 0x94
    def RD_Single_Circle_Angle(self):
        data = [0x94, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00]
        return data

    # Read motor status 1 and error flag commands 0x9A
    def RD_Motor_Status_1(self):
        data = [0x9A, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00]
        return data

    # Clear motor error flag command 0x9B
    def Clr_Error_flags(self):
        data = [0x9B, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00]
        return data

    # Read motor status 2 0x9C
    def RD_Motor_Status_2(self):
        data = [0x9C, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00]
        return data

    # Read motor status 3 0x9D
    def RD_Motor_Status_3(self):
        data = [0x9D, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00]
        return data

    # Motor off command 0x80
    def Motor_OFF(self):
        data = [0x80, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00]
        return data

    # Motor stop command 0x81
    def Motor_Stop(self):
        data = [0x81, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00]
        return data

    # Motor start command 0x88
    def Motor_Start(self):
        data = [0x88, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00]
        return data

    # Torque current control command 0xA1
    def Torque_Ctrl_Mode(self, Current):
        Current = bytearray.fromhex(
            f"{(Signed_int_to_hex((int((Current/32)*2000)), 16)[2:]):0>4}"
        )
        data = [0xA1, 0x00, 0x00, 0x00, Current[1], Current[0], 0x00, 0x00]
        return data

    # Speed control command 0xA2
    def Speed_Ctrl_Mode(self, Speed):
        Speed_SA1 = bytearray.fromhex(
            f"{(Signed_int_to_hex(int(Speed*600), 32)[2:]):0>8}"
        )
        data = [
            0xA2,
            0x00,
            0x00,
            0x00,
            Speed_SA1[3],
            Speed_SA1[2],
            Speed_SA1[1],
            Speed_SA1[0],
        ]
        return data

    # Position Control Mode 1 0xA3
    def Position_Ctrl_1(self, Angle):
        Angle = bytearray.fromhex(
            f"{(Signed_int_to_hex((int(Angle*600)), 32)[2:]):0>8}"
        )
        data = [0xA3, 0x00, 0x00, 0x00, Angle[3], Angle[2], Angle[1], Angle[0]]
        return data

    # Position Control Mode 2 0xA4
    def Position_Ctrl_2(self, Speed, Angle):
        Speed = bytearray.fromhex(f"{(hex(int(Speed*6))[2:]):0>4}")
        Angle = bytearray.fromhex(
            f"{(Signed_int_to_hex((int(Angle*600)), 32)[2:]):0>8}"
        )
        data = [0xA4, 0x00, Speed[1], Speed[0], Angle[3], Angle[2], Angle[1], Angle[0]]
        return data

    # Position Control Mode 3 0xA5
    def Position_Ctrl_3(self, Direction, Angle):
        if Direction == 0 or Direction == 1:
            Angle = bytearray.fromhex(f"{(hex(int(Angle*100))[2:]):0>4}")
            data = [0xA5, Direction, 0x00, 0x00, Angle[1], Angle[0], 0x00, 0x00]
            return data
        else:
            print("Enter the Right Format")

    # Position Control Mode 4 0xA6
    def Position_Ctrl_4(self, Direction, Speed, Angle):
        if Direction == 0 or Direction == 1:
            Speed = bytearray.fromhex(f"{(hex(int(Speed*6))[2:]):0>4}")
            Angle = bytearray.fromhex(f"{(hex(int(Angle*100))[2:]):0>4}")
            data = [0xA6, Direction, Speed[1], Speed[0], Angle[1], Angle[0], 0x00, 0x00]
            return data
        else:
            print("Enter the Right Format")

    # Position Control Mode 4 0xA7
    def Position_Ctrl_5(self, Angle):
        Angle = bytearray.fromhex(
            f"{(Signed_int_to_hex((int(Angle*600)), 32)[2:]):0>8}"
        )
        data = [0xA7, 0x00, 0x00, 0x00, Angle[3], Angle[2], Angle[1], Angle[0]]
        return data

    # Position Control Mode 4 0xA8
    def Position_Ctrl_6(self, Speed, Angle):
        Speed = bytearray.fromhex(f"{(hex(int(Speed*6))[2:]):0>4}")
        Angle = bytearray.fromhex(
            f"{(Signed_int_to_hex((int(Angle*600)), 32)[2:]):0>8}"
        )
        data = [0xA8, 0x00, Speed[1], Speed[0], Angle[3], Angle[2], Angle[1], Angle[0]]
        return data

    # Make the CAN Message
    def TX_Packet(self, motor_ID, send_data):
        if motor_ID <= 0 or send_data == None:
            print("Enter the Right ID or data")
        else:
            motor_ID = int(motor_ID)
            return can.Message(
                arbitration_id=320 + motor_ID, data=send_data, is_extended_id=False
            )

    # Function to send and receive the CAN Frame
    def Send_Receive_Message(self, TX_Packet):
        self.Send_Message(TX_Packet)
        while True:
            Temp_mesgrecv = self.Receive_Message()
            if ((TX_Packet.arbitration_id)) == Temp_mesgrecv.arbitration_id and (
                TX_Packet.data[0]
            ) == Temp_mesgrecv.data[0]:
                RX_Packet = Temp_mesgrecv
                self.decode_mesgrecv(RX_Packet)
                break

    # Function to Decode all the received Messages
    def decode_mesgrecv(self, Message):
        Array = [
            f"{(hex(Message.data[0])[2:]):0>2}",
            f"{(hex(Message.data[1])[2:]):0>2}",
            f"{(hex(Message.data[2])[2:]):0>2}",
            f"{(hex(Message.data[3])[2:]):0>2}",
            f"{(hex(Message.data[4])[2:]):0>2}",
            f"{(hex(Message.data[5])[2:]):0>2}",
            f"{(hex(Message.data[6])[2:]):0>2}",
            f"{(hex(Message.data[7])[2:]):0>2}",
        ]
        # Decode the Message of the Read PID Data 0x30
        # Decode the Message of PID Data After writing it to RAM 0x31
        # Decode the Message of PID Data After writing it to ROM 0x32
        if (
            Message.data[0] == 0x30
            or Message.data[0] == 0x31
            or Message.data[0] == 0x32
        ):
            if Message.data[0] == 0x30:
                print("Reading PID Data From Motor")
            elif Message.data[0] == 0x31:
                print("Wrote PID DATA to RAM")
            else:
                print("Wrote PID DATA to ROM")
            self.POSITION_LOOP_KP = int(Array[2], 16)
            self.POSITION_LOOP_KI = int(Array[3], 16)
            self.SPEED_LOOP_KP = int(Array[4], 16)
            self.SPEED_LOOP_KI = int(Array[5], 16)
            self.TORQUE_LOOP_KP = int(Array[6], 16)
            self.TORQUE_LOOP_KI = int(Array[7], 16)
            print(
                "Position loop Kp",
                self.POSITION_LOOP_KP,
                "\nPosition loop Ki",
                self.POSITION_LOOP_KI,
                "\nSpeed loop Kp",
                self.SPEED_LOOP_KP,
                "\nSpeed loop Ki",
                self.SPEED_LOOP_KI,
                "\nTorque loop Kp",
                self.TORQUE_LOOP_KP,
                "\nTorque loop Ki",
                self.TORQUE_LOOP_KI,
            )

        # Decode the Acceleration read Data 0x33
        # Decode the Acceleration Write Data 0x34
        elif Message.data[0] == 0x33 or Message.data[0] == 0x34:
            if Message.data[0] == 0x33:
                print("Reading Acceleration Data")
            else:
                print("Wrote Acceleration Data")
            self.ACCELERATION_IN = Signed_hex_to_int(
                (f"{Array[7]}{Array[6]}{Array[5]}{Array[4]}"), 32
            )
            self.ACCELERATION_OUT = self.ACCELERATION_IN / 6
            print("Acceleration is", self.ACCELERATION_OUT, "dps/s")

        # Decode the Encoder Read Data 0x90
        elif Message.data[0] == 0x90:
            print("Encoder Read Data")
            # Encoder Calculation
            self.ENCODER_POSITION = int((f"{Array[3]}{Array[2]}"), 16)
            # Encoder Raw Calculation
            self.ENCODER_ORIGINAL_POSITION = int((f"{Array[5]}{Array[4]}"), 16)
            # Encoder Offset Calculation
            self.ENCODER_OFFSET_POSITION = int((f"{Array[7]}{Array[6]}"), 16)
            print(
                "Encoder Position is",
                self.ENCODER_POSITION,
                "\nEncoder Raw Value is",
                self.ENCODER_ORIGINAL_POSITION,
                "\nEncoder offset is position",
                self.ENCODER_OFFSET_POSITION,
            )

        # Decode Write encoder offset command 0x91
        # Decode Write current position to ROM as motor zero position command 0x19
        elif Message.data[0] == 0x91 or Message.data[0] == 0x19:
            if Message.data[0] == 0x91:
                print("Wrote Encoder Offset")
            else:
                print("Wrote current position to ROM as motor zero position")
            self.ENCODER_OFFSET_POSITION = int((f"{Array[7]}{Array[6]}"), 16)
            print("Encoder offset position is", self.ENCODER_OFFSET_POSITION)

        # Decode Read multi turns angle Message 0x92
        elif Message.data[0] == 0x92:
            self.MULTI_TURN_ANG_IN = (
                Signed_hex_to_int(
                    (
                        f"{Array[7]}{Array[6]}{Array[5]}{Array[4]}{Array[3]}{Array[2]}{Array[1]}"
                    ),
                    56,
                )
                * 0.01
            )
            self.MULTI_TURN_ANG_OUT = self.MULTI_TURN_ANG_IN / 6
            self.MULTI_TURN_REV_IN = self.MULTI_TURN_ANG_IN / 360
            self.MULTI_TURN_REV_OUT = self.MULTI_TURN_ANG_OUT / 360
            # print('No of Turns of external Shaft =', self.MULTI_TURN_ANG_OUT, 'deg or', self.MULTI_TURN_REV_OUT,
            #       '\nNo of Turns of internal Shaft =', self.MULTI_TURN_ANG_IN, 'deg or', self.MULTI_TURN_REV_IN)

        # Decode Read single circle angle command 0x94
        elif Message.data[0] == 0x94:
            self.SINGLE_CIRCLE_ANG = (int(f"{Array[7]}{Array[6]}", 16)) * 0.01
            self.SINGLE_CIRCLE_REV = self.SINGLE_CIRCLE_ANG / 360
            print(
                "single turn Angle is",
                self.SINGLE_CIRCLE_ANG,
                "Deg",
                self.SINGLE_CIRCLE_REV,
                "rev",
            )

        # Decode Read motor status 1 and error flag commands 0x9A
        # Decode Message after clearing error Flags 0x9B
        elif Message.data[0] == 0x9A or Message.data[0] == 0x9B:
            if Message.data[0] == 0x9A:
                print("Error Flag Data")
            else:
                print("Cleared Error Flags")
            # Temperature Calculation
            self.TEMPERATURE = Signed_hex_to_int(Array[1], 8)
            print("Temperature is", self.TEMPERATURE)
            # Voltage Calculaion
            self.VOLTAGE = (int((f"{Array[4]}{Array[3]}"), 16)) * 0.1
            print("Voltage is", self.VOLTAGE)
            # Error
            Error_dict = {
                0: "No Error",
                1: "Low Voltage Error",
                4: "High Temperature Error",
                5: "Low Voltage & High Temperature Error",
            }
            self.ERROR_STATUS = Error_dict[int(Array[7], 16)]
            print("Error state is", self.ERROR_STATUS)

        # Decode Read Motor Status 3
        elif Message.data[0] == 0x9D:
            print("Reading Motor Status 3")
            # Phase A Current Calculation
            self.PHASE_A_CURRENT = Signed_hex_to_int(f"{Array[3]}{Array[2]}", 16) / 64
            print("Phase A Current", self.PHASE_A_CURRENT)
            # Phase B Current Calculation
            self.PHASE_B_CURRENT = Signed_hex_to_int(f"{Array[5]}{Array[4]}", 16) / 64
            print("Phase B Current", self.PHASE_B_CURRENT)
            # Phase C Current Calculation
            self.PHASE_C_CURRENT = Signed_hex_to_int((f"{Array[7]}{Array[6]}"), 16) / 64
            print("Phase C Current", self.PHASE_C_CURRENT)

        # Decode Motor OFF Message 0x80
        elif Message.data[0] == 0x80:
            print("Motor OFF")

        # Decode Motor Stop Message 0x81
        elif Message.data[0] == 0x81:
            self.MOTOR_STATUS = "Stopped"
            print("Motor is", self.MOTOR_STATUS)

        # Decode Motor Start Message 0x88
        elif Message.data[0] == 0x88:
            self.MOTOR_STATUS = "Started"
            print("Motor is", self.MOTOR_STATUS)

        # Decode Read Motor Data 2 Message 0x9C
        # Deocde the Torque Control Mode Received Data 0xA1
        # Deocde the Speed Control Mode Received Data 0xA2
        # Decode the Position Control Mode 1 Received Data 0xA3
        # Decode the Position Control Mode 2 Received Data 0xA4
        # Decode the Position Control Mode 3 Received Data 0xA5
        # Decode the Position Control Mode 4 Received Data 0xA6
        elif (
            Message.data[0] == 0x9C
            or Message.data[0] == 0xA1
            or Message.data[0] == 0xA2
            or Message.data[0] == 0xA3
            or Message.data[0] == 0xA4
            or Message.data[0] == 0xA5
            or Message.data[0] == 0xA6
            or Message.data[0] == 0xA7
            or Message.data[0] == 0xA8
        ):
            if Message.data[0] == 0x9C:
                print("Read Motor Status 2")
            elif Message.data[0] == 0xA1:
                print("Torque Control Mode")
            elif Message.data[0] == 0xA2:
                print("Speed Control Mode")
            elif Message.data[0] == 0xA3:
                print("Position Control Mode 1")
            elif Message.data[0] == 0xA4:
                # print('Position Control Mode 2')
                pass
            elif Message.data[0] == 0xA5:
                print("Position Control Mode 3")
            elif Message.data[0] == 0xA6:
                print("Position Control Mode 4")
            elif Message.data[0] == 0xA7:
                print("Position Control Mode 5")
            else:
                print("Position Control Mode 6")
            # Temperature Calculation
            self.TEMPERATURE = Signed_hex_to_int(Array[1], 8)
            # print("Temperature is",self.TEMPERATURE)
            # Torque Current Calculation
            self.TORQUE_CURRENT = (
                Signed_hex_to_int((f"{Array[3]}{Array[2]}"), 16) * 33
            ) / 2048
            # print('Torque Current is',self.TORQUE_CURRENT)
            # Speed Calculation
            self.SPEED_IN_DPS = Signed_hex_to_int((f"{Array[5]}{Array[4]}"), 16)
            self.SPEED_OUT_DPS = self.SPEED_IN_DPS / 6
            self.SPEED_IN_RPS = self.SPEED_IN_DPS / 360
            self.SPEED_OUT_RPS = self.SPEED_OUT_DPS / 360
            # print('Speed is', self.SPEED_OUT_DPS, 'dps', 'or', self.SPEED_OUT_RPS, 'rps')
            # Encoder Position Calculation
            self.ENCODER_POSITION = int((f"{Array[7]}{Array[6]}"), 16)
            # print('Encoder is at position', self.ENCODER_POSITION)
        else:
            print("Mesg Not Decoded")
