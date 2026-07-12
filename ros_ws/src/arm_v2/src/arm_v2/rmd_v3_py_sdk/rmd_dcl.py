#!/usr/bin/env python
# -*- coding: utf-8 -*-

########################################################
# This file contains all the output Variables of the RMD
# This file provides basic convertion functions
########################################################


class RMD_dcl:
    POSITION_LOOP_KP = None
    POSITION_LOOP_KI = None
    SPEED_LOOP_KP = None
    SPEED_LOOP_KI = None
    TORQUE_LOOP_KP = None
    TORQUE_LOOP_KI = None

    ACCELERATION_IN = None
    ACCELERATION_OUT = None

    MULTI_TURN_POSITION = None
    ENCODER_POSITION = None
    ENCODER_ORIGINAL_POSITION = None
    ENCODER_OFFSET_POSITION = None

    MULTI_TURN_ANG_IN = None
    MULTI_TURN_ANG_OUT = None
    MULTI_TURN_REV_IN = None
    MULTI_TURN_REV_OUT = None

    SINGLE_CIRCLE_ANG = None
    SINGLE_CIRCLE_REV = None

    POWER = None
    VOLTAGE = None
    ERROR_STATUS = None

    MOTOR_STATUS = None
    MOTOR_MODE = None

    TEMPERATURE = None
    TORQUE_CURRENT = None
    SPEED_IN_DPS = None
    SPEED_IN_RPS = None
    SPEED_OUT_DPS = None
    SPEED_OUT_RPS = None

    PHASE_A_CURRENT = None
    PHASE_B_CURRENT = None
    PHASE_C_CURRENT = None
    Brake_status = None

    RUNTIME = None
    Version_Date = None
    Comm_Interrupt_time = None


# Converter from Hex to Dec(Signed)
def Signed_hex_to_int(hexval, bits):
    val = int(hexval, 16)
    if val & (1 << (bits - 1)):
        val -= 1 << bits
    return val


# Converter from Dec to Hex(Signed)
def Signed_int_to_hex(val, nbits):
    return hex((val + (1 << nbits)) % (1 << nbits))
