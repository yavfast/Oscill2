This reference guide details the properties, registers, commands, and communication protocol for the Oscilloscope (Oscill) device, based on the provided documents.

---

# Oscilloscope (Oscill) Communication Reference Guide

## 1. Introduction and Concepts

The communication between the Oscilloscope (Oscill) and the controlling computer (Comp) is based on the **OBEX protocol** with some permitted private extensions. The Oscill acts as the **server**, responding to requests from the Comp, which acts as the **client**.

### 1.1 Device Roles
| Term | Role/Description |
| :--- | :--- |
| **Oscill** | Portable oscilloscope (may be full or peripheral). Acts as the **server**. |
| **Comp** | Control device and result display unit (client). Can be a PC (MS Windows/DOS), PDA, or mobile phone. |

### 1.2 Data Concepts
| Term | Description | Source |
| :--- | :--- | :--- |
| **Property** | Oscill characteristics that cannot be changed by the client. They are read-only. |
| **Register** | Parameters available for reading and writing, used for configuring device operation. Reading a register returns the actual configured setting, which may differ from the value written. |
| **Sampling Period** | The interval between samples in the resulting output array. Note: This differs from the ADC sampling frequency, as ADC sampling occurs at maximum possible speed to combat aliasing. |
| **Stroboscopic Delay** | The time interval from the synchronization condition occurring to the nearest ADC clock pulse when the ADC delivers a sample. |

## 2. Oscill Properties (Read-Only)

Oscill properties detail the device's characteristics and capabilities.

### 2.1 System Properties (1.1)
| Property Name | Description | Format/Units | Example (Base Model) | Source |
| :--- | :--- | :--- | :--- | :--- |
| **VHD** | Version of the digital circuit part of the Oscill. | 4 ASCII bytes (X.XX format). | N/A | |
| **VHA** | Version of the analog circuit part of the Oscill. | 4 ASCII bytes (X.XX format). | N/A | |
| **VSD** | Version of the digitizer (firmware part controlling ADC, analog, CPU, port settings). | 4 ASCII bytes (X.XX format). | N/A | |
| **VSI** | Version of the user interface (firmware part handling GUI, LCD, high-level processing). | 4 ASCII bytes (X.XX format). | N/A | |
| **VSC** | Version of the connector (firmware part handling bidirectional Comp connection and interface initialization). | 4 ASCII bytes (X.XX format). | N/A | |
| **VSO** | Version of the OBEX module (firmware part managing OBEX protocols and command execution). | 4 ASCII bytes (X.XX format). | N/A | |
| **MCd** | Default machine cycle duration (ensures stable operation). | 2 bytes, unsigned. Unit: 10 ps. | 0x07D0 (50 MHz clock). | |
| **MCl** | Minimum machine cycle duration (overclocking capability). | 2 bytes, unsigned. Unit: 10 ps. | 0x03E8 (100 MHz clock). | |

### 2.2 Sampling Properties (1.2)
| Property Name | Description | Format/Units | Example (Base Model) | Source |
| :--- | :--- | :--- | :--- | :--- |
| **TOl** | Minimum period for single (realtime) sampling. Sampling faster than TOl requires TS values listed in TOv. | 2 bytes. Unit: machine cycles \* 256. | 0x2000. | |
| **TOv** | Bit map of fast single (realtime) sampling options that are faster than TOl. | 4 bytes, bitwise (1=provided, 0=not provided). | 00000001 00000100. | |
| **TMl** | Minimum period for strobed (RIS) equivalent sampling. | 2 bytes, unsigned. Unit: machine cycles \* 256. | 0x0010. | |
| **TMh** | Maximum period for strobed (RIS) equivalent sampling. | 2 bytes, unsigned. Unit: machine cycles \* 256. | 0x0100. | |
| **TPl** | Minimum period for parallel/infinite sampling (when averaging/peak/statistical modes are off). | 4 bytes, unsigned. Unit: machine cycles \* 256. | 0x01000000. | |
| **TCh** | Maximum number of presamples possible before the synchronization moment. | 2 bytes, unsigned. Unit: sample (1 or 2 bytes). | N/A | |
| **QSh** | Maximum size of the output array that can be returned for the current sampling settings. | 2 bytes, unsigned. Unit: sample (1 or 2 bytes). | N/A | |

### 2.3 Channel 1 Properties (1.3)
| Property Name | Description | Format/Units | Example (Base Model) | Source |
| :--- | :--- | :--- | :--- | :--- |
| **V1h / V1l** | Maximum / Minimum channel sensitivity. | 2 bytes, unsigned. Unit: 8 mV / ADC range. | V1h=0x2710 (10V/div), V1l=0x0014 (20mV/div). | |
| **P1h / P1l** | Maximum / Minimum offset of the ADC input range relative to 0. | 2 bytes, signed. Unit: 1/256th of the ADC range. | P1h=0x0180, P1l=0xFE80. | |
| **D1m** | Channel synchronization delay (constructive delay). | 2 bytes. Unit: 10 picoseconds. | N/A | |

## 3. Oscill Registers (Read/Write)

Registers are used to configure the device. Changes to one register may affect others, so dependent registers must also be read back after an alteration.

### 3.1 System Registers (2.1)
| Register Name | Description | Format/Units | Dependencies | Source |
| :--- | :--- | :--- | :--- | :--- |
| **MC** | Machine Cycle Duration of the controller. | 2 bytes, unsigned. Unit: 10 ps. | None. | |

### 3.2 Sweep Control Registers (2.2)
| Register Name | Description | Format/Units | Dependencies | Source |
| :--- | :--- | :--- | :--- | :--- |
| **TS** | Sampling Period: Interval between samples in the returned array. | 4 bytes, unsigned. Unit: machine cycles \* 256. | High priority (affects RS, M1, TD). | |
| **RS** | Sampling Method. Bit 0: Single (0) or Strobed (1). Bit 1: Transfer after digitization (0) or Parallel transfer (1). Bit 2: Buffered (0) or Infinite/Roll (1). | 1 byte, bitwise. | Depends on TS. Affects TD, M1. | |
| **AP** | Number of passes for averaging/peak mode. Stored value is $2^N - 1$ (1 to 256 passes). | 1 byte. | Depends on RS (only possible in single or strobed mode). Affects QS, QSh. | |
| **QS** | Size of the sample array returned. Max value defined by QSh. | 2 bytes, unsigned. | Depends on RS, TS, M1. | |
| **TD** | Sweep Delay: Delay between synchronization and start of digitization. | 4 bytes, unsigned. Unit: 12 machine cycles. | Depends on RS, TS, QS. | |
| **TC** | Sweep Centering: Interval between the first sample and the synchronization moment. | 2 bytes, unsigned. Unit: samples (current interval between samples). | Depends on RS, TS, QS. | |
| **RT** | Trigger Type. Bits 1 0: Auto (00), Waiting (01), Free (10), Infinitely Waiting (11). | 1 byte, bitwise. | Affects use of TA or TW registers. | |
| **TA** | Maximum time sync is awaited in **Auto Trigger** mode (RT=0). If time expires, digitization starts without sync. | 4 bytes, unsigned. Unit: 12 machine cycles. | None. | |
| **TW** | Maximum time sync is awaited in **Waiting Trigger** mode (RT=1). If time expires, an error is returned. | 4 bytes, unsigned. Unit: 12 machine cycles. | None. | |
| **AR** | Minimum number of passes with the same delay permitted in **Strobed Mode** (RIS). | 1 byte, unsigned. | None. | |

### 3.3 Channel 1 Control Registers (2.3)
| Register Name | Description | Format/Units | Dependencies | Source |
| :--- | :--- | :--- | :--- | :--- |
| **O1** | Hardware Channel Mode. Includes settings for Input Grounded, AC/AC+DC coupling, 3 MHz filter, and 3 kHz filter. | 1 byte. | None. | |
| **V1** | Channel Sensitivity (sets input amplifier gain). Range is bounded by V1h and V1l properties. | 2 bytes, unsigned. Unit: 8.53 mV / ADC range. | Depends on O1 (grounded input cancels sensitivity). Affects P1, P1h/P1l. | |
| **P1** | Channel Offset: Shift of the ADC input range relative to 0. Range is bounded by P1h and P1l properties. | 2 bytes, signed. Unit: 1/256th of the ADC input range. | Depends on V1. | |
| **M1** | Software Channel Mode / Sample Processing Mode (performed in Oscill). Defines averaging modes (1-byte or 2-byte resolution), peak modes, or normal ADC sample output. | 1 byte. | Depends on RS, TS. Affects QS, QSh. | |
| **T1** | Channel Synchronization Use. Defines rising/falling edge sync use, hysteresis control, and HF/LF synchronization modes. | 1 byte. | None. | |
| **S1** | Channel Synchronization Level. The level at which the synchronization event occurs. | 1 byte, unsigned. Unit: 1/256th of the ADC range. | None. | |

## 4. Oscill Commands

Commands force the Oscill to perform an action (Identifier header: 0x72).

### 4.1 Calibration Command ('C')
*   **Action:** Oscill performs self-calibration, including scaling and zeroing the channel shift and synchronization level relative to the ADC input range.
*   **Packet:** PUT request with header 0x72 “C”.
*   **Response:** Success package upon successful calibration.

### 4.2 Digitization Command ('D')
*   **Action:** Initiates synchronization waiting, presampling, digitization, and data return.
*   **Packet:** GET request with header 0x72 “D”.
*   **Response:** Success package with header 0x72 “D” and digitization results in header **0x49**.

| Mode Description | Register Setting (RS) | Application | Source |
| :--- | :--- | :--- | :--- |
| Single Shot + Auto Trigger | 0b00000000 | Investigating single-shot or periodic signals. | |
| Single Shot + Waiting Trigger | 0b00001000 | Investigating single-shot or periodic signals. | |
| Strobed (RIS) Acquisition | 0b00000001 | Investigating high-frequency periodic signals. | |
| Parallel + Auto Trigger | 0b00000010 | Low-frequency single-shot or periodic signals. | |
| Parallel + Waiting Trigger | 0b00001010 | Low-frequency single-shot or periodic signals. | |
| Infinite (Roll) Acquisition | 0b0000X011 | Low-frequency signals over an infinite time interval. | |

*In Roll mode, data is returned via a **Continue** Response packet. The Comp must send an **Abort** package (0xFF) to stop the data stream.*

### 4.3 Firmware Load Command ('F')
*   **Action:** Used to load a fragment of the firmware.
*   **Packet:** GET request with header 0x72 “F”.
*   **Response:** Success package upon successful loading of the fragment.

## 5. Data Formats and Attributes

The digitization results are returned in the OBEX header **0x49**. The format consists of attributes followed by the sample array data.

### 5.1 Output Array Structure
1.  **2 bytes:** Digitization Attributes (sweep and synchronization description).
2.  **Per Channel:**
    *   **2 bytes:** Channel Attributes (sample array format).
    *   **2 bytes:** Sample array size (in bytes).
    *   **XX bytes:** Channel sample array.

### 5.2 Digitization Attributes (First Byte)
| Bits | Value | Description | Source |
| :--- | :--- | :--- | :--- |
| **Bit 0** | 0 / 1 | Used Sampling Method: 0 = Single (realtime), 1 = Strobed (RIS). | |
| **Bit 1** | 0 / 1 | Parallelism: 0 = Arrays fully digitized, 1 = Array transmitted during digitization. | |
| **Bit 2** | 0 / 1 | Infinity: 0 = Finite array size, 1 = Infinite acquisition (Roll mode). | |
| **Bits 5 4** | 00 | Trigger Source: Timeout (Auto trigger after TA). | |
| **Bits 5 4** | 01 | Trigger Source: Synchronization condition met (Falling edge). | |
| **Bits 5 4** | 10 | Trigger Source: Synchronization condition met (Rising edge). | |
| **Bits 7 6** | 00/01/10/11 | Number of Channels: 00=1, 01=2, 10=3, 11=4. | |

*The Second byte of Digitization Attributes is reserved.*

### 5.3 Channel Attributes (First Byte)
| Bits 210 | Description (Sample Format) | Bytes per Sample | Source |
| :--- | :--- | :--- | :--- |
| **100** | Averaging (LSBs discarded) | 1 byte. | |
| **001** | High resolution mode (Averaging) | 2 bytes. | |
| **010** | Peak mode (interlaced: min/max alternating) | 1 byte. | |
| **011** | Peak mode (min and max paired) | 2 bytes. | |
| **100** | Normal mode (ADC sample equals output array sample) | 1 byte. | |

*The Second byte of Channel Attributes is reserved.*

### 5.4 Sample Array Format
*   **Averaging Mode:** Sequence of 8-bit unsigned samples, where each sample is the average over the discretization interval.
*   **Peak Mode:** Sequence of 8-bit unsigned sample pairs. The odd sample is the minimum value, and the even sample is the maximum value for the discretization interval.
*   **Statistical Mode:** To be defined later.

## 6. OBEX Protocol Details and Extensions

The OBEX protocol manages the exchange of packets containing headers.

### 6.1 Packet Types and Operation Codes

| Packet Type | Direction | Key OBEX Opcode (Client Request) | Key OBEX Response Code (Server) | Source |
| :--- | :--- | :--- | :--- | :--- |
| **Connect** | Client $\to$ Server | 0x80 (Start Session) | 0xA0 (Success) | |
| **Disconnect** | Client $\to$ Server | 0x81 (End Session) | N/A | |
| **Put** | Client $\to$ Server | 0x02 / 0x82 (Send object/data) | 0xA0 (Success) | |
| **Get** | Client $\to$ Server | 0x03 / 0x83 (Receive object/data) | 0xA0 (Success), 0x90 (Continue) | |
| **Abort** | Client $\to$ Server | 0xFF (Stop current operation) | N/A | |

**Oscill Extensions (Client Request Codes):**
*   **0x91:** Change serial port speed.
*   **0x92:** Repeat the last Response packet.

**Server Response Codes:**
*   **0x10 / 0x90 (Continue):** Server returns part of the requested long data (client should send another Get request).
*   **0x20 / 0xA0 (Success):** Server completed the task and returns all requested data.
*   **0x40 / 0xC0 (Bad Request):** Server did not understand the request.
*   **0x51 / 0xD1 (Not Implemented):** The requested function does not exist in the server.

### 6.2 Key OBEX Headers (Oscill Extensions)

Headers are components of OBEX packets. Their interpretation depends on the first two MSBs of the Identifier.

| Identifier (Hex) | Type | Description | Usage | Source |
| :--- | :--- | :--- | :--- | :--- |
| **0x70** | Byte Sequence (Oscill Ext.) | **Oscill Property Name** (ASCII, 3 chars). Properties are read-only (GET). | Used when requesting properties like VHD. | |
| **0x71** | Byte Sequence (Oscill Ext.) | **Oscill Register Name** (ASCII, 2 chars). Registers are R/W (GET/PUT). | Used when setting or reading registers like TS or V1. | |
| **0x72** | Byte Sequence (Oscill Ext.) | **Oscill Command** (1 ASCII character, e.g., 'C' or 'D'). | Used to initiate commands like Calibration or Digitization. | |
| **0x49** | Byte Sequence | **Object Body (or final part)**. | Contains the output sample array upon Digitization command ('D'). | |
| **0xB0** | 1-Byte Number (Oscill Ext.) | **Checksum.** Value ensures the sum of all bytes in the packet (including 0xB0) modulo 256 equals 0. Optional, but enhances reliability. | Used for error correction. | |
| **0xB1** | 1-Byte Number (Oscill Ext.) | **1-byte Oscill value** (register/property). | Used to transmit 1-byte register values. | |
| **0xF0** | 4-Byte Number (Oscill Ext.) | **2-byte Oscill value** (register/property). | N/A | |
| **0xF1** | 4-Byte Number (Oscill Ext.) | **4-byte Oscill value** (register/property). | Used to transmit 4-byte register values (e.g., TS). | |

### 6.3 Error Correction
The optional Checksum header (0xB0) allows the receiving side to verify data integrity.

*   **Corrupted Request:** If the Server (Oscill) detects a corrupted request packet, it returns `0xD0` (Internal Server Error). The Client (Comp) should repeat the request once.
*   **Corrupted Response:** If the Client (Comp) receives a response with an incorrect checksum or length, it can request a repetition of the last response using the request opcode **0x92**.
*   **No Response:** If the Server fails to respond (due to being busy, disconnected, or packet loss), the Client can repeat the request after a protective timeout interval, which must account for the duration of the server's potential non-interruptible actions (like long digitization cycles).
