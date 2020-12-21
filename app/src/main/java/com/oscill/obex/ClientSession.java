/*
 * Copyright (c) 2015 The Android Open Source Project
 * Copyright (C) 2015 Samsung LSI
 * Copyright (c) 2008-2009, Motorola, Inc.
 *
 * All rights reserved.
 *
 * Redistribution and use in source and binary forms, with or without
 * modification, are permitted provided that the following conditions are met:
 *
 * - Redistributions of source code must retain the above copyright notice,
 * this list of conditions and the following disclaimer.
 *
 * - Redistributions in binary form must reproduce the above copyright notice,
 * this list of conditions and the following disclaimer in the documentation
 * and/or other materials provided with the distribution.
 *
 * - Neither the name of the Motorola, Inc. nor the names of its contributors
 * may be used to endorse or promote products derived from this software
 * without specific prior written permission.
 *
 * THIS SOFTWARE IS PROVIDED BY THE COPYRIGHT HOLDERS AND CONTRIBUTORS "AS IS"
 * AND ANY EXPRESS OR IMPLIED WARRANTIES, INCLUDING, BUT NOT LIMITED TO, THE
 * IMPLIED WARRANTIES OF MERCHANTABILITY AND FITNESS FOR A PARTICULAR PURPOSE
 * ARE DISCLAIMED. IN NO EVENT SHALL THE COPYRIGHT HOLDER OR CONTRIBUTORS BE
 * LIABLE FOR ANY DIRECT, INDIRECT, INCIDENTAL, SPECIAL, EXEMPLARY, OR
 * CONSEQUENTIAL DAMAGES (INCLUDING, BUT NOT LIMITED TO, PROCUREMENT OF
 * SUBSTITUTE GOODS OR SERVICES; LOSS OF USE, DATA, OR PROFITS; OR BUSINESS
 * INTERRUPTION) HOWEVER CAUSED AND ON ANY THEORY OF LIABILITY, WHETHER IN
 * CONTRACT, STRICT LIABILITY, OR TORT (INCLUDING NEGLIGENCE OR OTHERWISE)
 * ARISING IN ANY WAY OUT OF THE USE OF THIS SOFTWARE, EVEN IF ADVISED OF THE
 * POSSIBILITY OF SUCH DAMAGE.
 */

package com.oscill.obex;

import android.os.SystemClock;

import androidx.annotation.NonNull;
import androidx.annotation.Nullable;

import java.io.ByteArrayOutputStream;
import java.io.IOException;
import java.io.InputStream;
import java.io.OutputStream;

/**
 * This class in an implementation of the OBEX ClientSession.
 */
public final class ClientSession implements ObexSession {

    private static final String TAG = "ClientSession";

    private boolean mOpen;

    // Determines if an OBEX layer connection has been established
    private boolean mObexConnected;

    private int mMaxTxPacketSize = ObexHelper.LOWER_LIMIT_MAX_PACKET_SIZE;

    private boolean mRequestActive;

    private final InputStream mInput;

    private final OutputStream mOutput;

    private final ObexTransport mTransport;

    public ClientSession(@NonNull ObexTransport trans) throws IOException {
        mInput = trans.openInputStream();
        mOutput = trans.openOutputStream();
        mOpen = true;
        mRequestActive = false;
        mTransport = trans;
    }

    @NonNull
    public InputStream getInput() {
        return mInput;
    }

    @NonNull
    public OutputStream getOutput() {
        return mOutput;
    }

    public void checkConnected() throws IOException {
        if (!mObexConnected) {
            throw new IOException("Not connected to the server");
        }
    }

    public void checkDisconnected() throws IOException {
        if (mObexConnected) {
            throw new IOException("Already connected to server");
        }
    }

    public void reset() throws IOException {
        ensureOpen();

        checkDisconnected();

        setRequestActive();

        sendRequest(ObexHelper.OBEX_OPCODE_ABORT, null);
        SystemClock.sleep(500L); // Wait for reset device

        setRequestInactive();
    }

    public void setSpeed(byte speed) throws IOException {
        ensureOpen();
        setRequestActive();

        sendRequest(Header.OSCILL_SPEED, new byte[]{speed});
        readResponse(Header.OSCILL_SPEED, new HeaderSet());

        setRequestInactive();
    }

    @NonNull
    public HeaderSet connect(@Nullable HeaderSet header) throws IOException {
        ensureOpen();

        checkDisconnected();

        setRequestActive();

        int totalLength = 4;
        byte[] head = null;

        // Determine the header byte array
        if (header != null) {
            head = ObexHelper.createHeader(header, false);
            totalLength += head.length;
        }
        /*
        * Write the OBEX CONNECT packet to the server.
        * Byte 0: 0x80
        * Byte 1&2: Connect Packet Length
        * Byte 3: OBEX Version Number (Presently, 0x10)
        * Byte 4: Flags (For TCP 0x00)
        * Byte 5&6: Max OBEX Packet Length (Defined in MAX_PACKET_SIZE)
        * Byte 7 to n: headers
        */
        byte[] requestPacket = new byte[totalLength];
        int maxRxPacketSize = mTransport.getMaxReceivePacketSize();
        // We just need to start at  byte 3 since the sendRequest() method will
        // handle the length and 0x80.
        requestPacket[0] = (byte)0x10;
        requestPacket[1] = (byte)0x00;
        requestPacket[2] = (byte)(maxRxPacketSize >> 8);
        requestPacket[3] = (byte)(maxRxPacketSize & 0xFF);
        if (head != null) {
            System.arraycopy(head, 0, requestPacket, 4, head.length);
        }

        HeaderSet returnHeaderSet = new HeaderSet();
        sendRequest(ObexHelper.OBEX_OPCODE_CONNECT, requestPacket, returnHeaderSet);

        /*
        * Read the response from the OBEX server.
        * Byte 0: Response Code (If successful then OBEX_HTTP_OK)
        * Byte 1&2: Packet Length
        * Byte 3: OBEX Version Number
        * Byte 4: Flags3
        * Byte 5&6: Max OBEX packet Length
        * Byte 7 to n: Optional HeaderSet
        */
        if (returnHeaderSet.responseCode == ResponseCodes.OBEX_HTTP_OK) {
            mObexConnected = true;
        }
        setRequestInactive();

        return returnHeaderSet;
    }

    @NonNull
    public ClientOperation get(@NonNull HeaderSet header) throws IOException {
        checkConnected();
        setRequestActive();
        ensureOpen();

        return new ClientOperation(this, header, ClientOperation.OperationType.GET, mMaxTxPacketSize);
    }

    @NonNull
    public HeaderSet delete(@Nullable HeaderSet header) throws IOException {
        Operation op = put(header);
        op.getResponse();
        HeaderSet returnValue = op.getReceivedHeader();
        op.close();

        return returnValue;
    }

    @NonNull
    public HeaderSet disconnect(@Nullable HeaderSet header) throws IOException {
//        checkConnected();
        setRequestActive();
        ensureOpen();

        byte[] head = null;
        if (header != null) {
            head = ObexHelper.createHeader(header, false);
        }

        HeaderSet returnHeaderSet = new HeaderSet();
        sendRequest(ObexHelper.OBEX_OPCODE_DISCONNECT, head, returnHeaderSet);

        /*
         * An OBEX DISCONNECT reply from the server:
         * Byte 1: Response code
         * Bytes 2 & 3: packet size
         * Bytes 4 & up: headers
         */

        /* response code , and header are ignored
         * */

        synchronized (this) {
            mObexConnected = false;
            setRequestInactive();
        }

        return returnHeaderSet;
    }

    @NonNull
    public ClientOperation put(@NonNull HeaderSet header) throws IOException {
        checkConnected();
        setRequestActive();

        ensureOpen();

        return new ClientOperation(this, header, ClientOperation.OperationType.PUT, mMaxTxPacketSize);
    }

    @NonNull
    public ClientOperation exec(@NonNull ClientOperation.OperationType operationType, @NonNull HeaderSet header) throws IOException {
        checkConnected();
        setRequestActive();

        ensureOpen();

        return new ClientOperation(this, header, operationType, mMaxTxPacketSize);
    }


    /**
     * Verifies that the connection is open.
     * @throws IOException if the connection is closed
     */
    public synchronized void ensureOpen() throws IOException {
        if (!mOpen) {
            throw new IOException("Connection closed");
        }
    }

    /**
     * Set request inactive. Allows Put and get operation objects to tell this
     * object when they are done.
     */
    /*package*/synchronized void setRequestInactive() {
        mRequestActive = false;
    }

    /**
     * Set request to active.
     * @throws IOException if already active
     */
    private synchronized void setRequestActive() throws IOException {
        if (mRequestActive) {
            throw new IOException("OBEX request is already being performed");
        }
        mRequestActive = true;
    }

    private void sendRequest(int opCode, @Nullable byte[] head) throws IOException {
        ByteArrayOutputStream out = new ByteArrayOutputStream();
        out.write((byte)opCode);

        // Determine if there are any headers to send
        if (head == null) {
            out.write(0x00);
            out.write(0x03);
        } else {
            int packetLen = head.length + 3;
            out.write((byte)(packetLen >> 8));
            out.write((byte)packetLen);
            out.write(head);
        }

        // Write the request to the output stream and flush the stream
        OutputStream output = getOutput();
        output.write(out.toByteArray());
        output.flush();
    }

    private void readResponse(int opCode, @NonNull HeaderSet headerSet) throws IOException {
        InputStream input = getInput();
        try {
            headerSet.responseCode = read(input);

            /* len_hi | len_lo */
            byte[] header = read(input, 2);
            int length = ObexHelper.convertToInt(header);

            if (length <= ObexHelper.BASE_PACKET_LENGTH) {
                return;
            }

            if (length > mTransport.getMaxReceivePacketSize()) {
                throw new IOException("Packet received exceeds packet size limit");
            }

            length -= header.length + 1/*response code*/;

            byte[] data;

            switch (opCode) {
                case ObexHelper.OBEX_OPCODE_CONNECT:
                    data = readConnectResponse(length);
                    break;

                default:
                    data = read(input, length);
                    break;
            }

            ObexHelper.updateHeaderSet(headerSet, data);

        } finally {
            input.reset();
        }

    }

    private static int read(@NonNull InputStream input) throws IOException {
        return input.read();
    }

    @NonNull
    private static byte[] read(@NonNull InputStream input, int length) throws IOException {
        if (length > 0) {
            byte[] data = new byte[length];
            if (input.read(data, 0, length) > 0) {
                return data;
            }
            throw new IOException("Read data error");
        }

        return new byte[]{};
    }

    @NonNull
    private byte[] readConnectResponse(int length) throws IOException {
        InputStream input = getInput();

        /* version | flags | len_hi | len_lo */
        byte[] header = read(input, 4);
        mMaxTxPacketSize = ObexHelper.convertToInt(new byte[]{header[2], header[3]});

        length -= header.length;
        return read(input, length);
    }

    /**
     * Sends a standard request to the client. It will then wait for the reply
     * and update the header set object provided. If any authentication headers
     * (i.e. authentication challenge or authentication response) are received,
     * they will be processed.
     * @param opCode the type of request to send to the client
     * @param head the headers to send to the client
     * @param header the header object to update with the response
     * @throws IOException if an IO error occurs
     */
    public void sendRequest(int opCode, @Nullable byte[] head, @NonNull HeaderSet header) throws IOException {
        sendRequest(opCode, head, header, 0);
    }

    public void sendRequest(int opCode, @Nullable byte[] head, @NonNull HeaderSet header, int responseTimeout) throws IOException {
        sendRequest(opCode, head);

        if (responseTimeout > 0L) {
            SystemClock.sleep(responseTimeout);
        }

        readResponse(opCode, header);
    }

    public void close() throws IOException {
        mOpen = false;
        mInput.close();
        mOutput.close();
    }

}
