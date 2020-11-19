/*
 * Copyright (c) 2014 The Android Open Source Project
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

import androidx.annotation.NonNull;
import androidx.annotation.Nullable;

import java.io.ByteArrayOutputStream;
import java.io.IOException;
import java.util.Calendar;
import java.security.SecureRandom;
import java.util.HashMap;
import java.util.LinkedHashMap;
import java.util.Map;

/**
 * This class implements the com.oscill.obex.HeaderSet interface for OBEX over
 * RFCOMM or OBEX over l2cap.
 * @hide
 */
public final class HeaderSet {

    /**
     * Represents the OBEX Count header. This allows the connection statement to
     * tell the server how many objects it plans to send or retrieve.
     * <P>
     * The value of <code>COUNT</code> is 0xC0 (192).
     */
    public static final int COUNT = 0xC0;

    /**
     * Represents the OBEX Name header. This specifies the name of the object.
     * <P>
     * The value of <code>NAME</code> is 0x01 (1).
     */
    public static final int NAME = 0x01;

    /**
     * Represents the OBEX Type header. This allows a request to specify the
     * type of the object (e.g. text, html, binary, etc.).
     * <P>
     * The value of <code>TYPE</code> is 0x42 (66).
     */
    public static final int TYPE = 0x42;

    /**
     * Represents the OBEX Length header. This is the length of the object in
     * bytes.
     * <P>
     * The value of <code>LENGTH</code> is 0xC3 (195).
     */
    public static final int LENGTH = 0xC3;

    /**
     * Represents the OBEX Time header using the ISO 8601 standards. This is the
     * preferred time header.
     * <P>
     * The value of <code>TIME_ISO_8601</code> is 0x44 (68).
     */
    public static final int TIME_ISO_8601 = 0x44;

    /**
     * Represents the OBEX Time header using the 4 byte representation. This is
     * only included for backwards compatibility. It represents the number of
     * seconds since January 1, 1970.
     * <P>
     * The value of <code>TIME_4_BYTE</code> is 0xC4 (196).
     */
    public static final int TIME_4_BYTE = 0xC4;

    /**
     * Represents the OBEX Description header. This is a text description of the
     * object.
     * <P>
     * The value of <code>DESCRIPTION</code> is 0x05 (5).
     */
    public static final int DESCRIPTION = 0x05;

    /**
     * Represents the OBEX Target header. This is the name of the service an
     * operation is targeted to.
     * <P>
     * The value of <code>TARGET</code> is 0x46 (70).
     */
    public static final int TARGET = 0x46;

    /**
     * Represents the OBEX HTTP header. This allows an HTTP 1.X header to be
     * included in a request or reply.
     * <P>
     * The value of <code>HTTP</code> is 0x47 (71).
     */
    public static final int HTTP = 0x47;

    /**
     * Represents the OBEX BODY header.
     * <P>
     * The value of <code>BODY</code> is 0x48 (72).
     */
    public static final int BODY = 0x48;

    /**
     * Represents the OBEX End of BODY header.
     * <P>
     * The value of <code>BODY</code> is 0x49 (73).
     */
    public static final int END_OF_BODY = 0x49;

    /**
     * Represents the OBEX Who header. Identifies the OBEX application to
     * determine if the two peers are talking to each other.
     * <P>
     * The value of <code>WHO</code> is 0x4A (74).
     */
    public static final int WHO = 0x4A;

    /**
     * Represents the OBEX Connection ID header. Identifies used for OBEX
     * connection multiplexing.
     * <P>
     * The value of <code>CONNECTION_ID</code> is 0xCB (203).
     */

    public static final int CONNECTION_ID = 0xCB;

    /**
     * Represents the OBEX Application Parameter header. This header specifies
     * additional application request and response information.
     * <P>
     * The value of <code>APPLICATION_PARAMETER</code> is 0x4C (76).
     */
    public static final int APPLICATION_PARAMETER = 0x4C;

    /**
     * Represents the OBEX authentication digest-challenge.
     * <P>
     * The value of <code>AUTH_CHALLENGE</code> is 0x4D (77).
     */
    public static final int AUTH_CHALLENGE = 0x4D;

    /**
     * Represents the OBEX authentication digest-response.
     * <P>
     * The value of <code>AUTH_RESPONSE</code> is 0x4E (78).
     */
    public static final int AUTH_RESPONSE = 0x4E;

    /**
     * Represents the OBEX Object Class header. This header specifies the OBEX
     * object class of the object.
     * <P>
     * The value of <code>OBJECT_CLASS</code> is 0x4F (79).
     */
    public static final int OBJECT_CLASS = 0x4F;

    /**
     * Represents the OBEX Single Response Mode (SRM). This header is used
     * for Single response mode, introduced in OBEX 1.5.
     * <P>
     * The value of <code>SINGLE_RESPONSE_MODE</code> is 0x97 (151).
     */
    public static final int SINGLE_RESPONSE_MODE = 0x97;

    /**
     * Represents the OBEX Single Response Mode Parameters. This header is used
     * for Single response mode, introduced in OBEX 1.5.
     * <P>
     * The value of <code>SINGLE_RESPONSE_MODE_PARAMETER</code> is 0x98 (152).
     */
    public static final int SINGLE_RESPONSE_MODE_PARAMETER = 0x98;

    public static final int OSCILL_PROPERTY = 0x70;
    public static final int OSCILL_REGISTRY = 0x71;
    public static final int OSCILL_DATA = 0x72;
    public static final int OSCILL_CRC = 0xB0;
    public static final int OSCILL_1BYTE = 0xB1;
    public static final int OSCILL_2BYTE = 0xF0;
    public static final int OSCILL_4BYTE = 0xF1;

    private Map<Integer,byte[]> headerMap = new LinkedHashMap<>();
    public int responseCode = -1;

    /**
     * Creates new <code>HeaderSet</code> object.
     */
    public HeaderSet() {
    }

    /**
     * Sets the value of the header identifier to the value provided. The type
     * of object must correspond to the Java type defined in the description of
     * this interface. If <code>null</code> is passed as the
     * <code>headerValue</code> then the header will be removed from the set of
     * headers to include in the next request.
     * @param headerID the identifier to include in the message
     * @param headerValue the value of the header identifier
     * @throws IllegalArgumentException if the header identifier provided is not
     *         one defined in this interface or a user-defined header; if the
     *         type of <code>headerValue</code> is not the correct Java type as
     *         defined in the description of this interface\
     */
    public void setHeader(int headerID, @Nullable byte[] headerValue) {
        headerMap.put(headerID, headerValue);
    }

    /**
     * Retrieves the value of the header identifier provided. The type of the
     * Object returned is defined in the description of this interface.
     * @param headerID the header identifier whose value is to be returned
     * @return the value of the header provided or <code>null</code> if the
     *         header identifier specified is not part of this
     *         <code>HeaderSet</code> object
     * @throws IllegalArgumentException if the <code>headerID</code> is not one
     *         defined in this interface or any of the user-defined headers
     * @throws IOException if an error occurred in the transport layer during
     *         the operation or if the connection has been closed
     */
    @Nullable
    public byte[] getHeader(int headerID) {
        return headerMap.get(headerID);
    }

    /**
     * Retrieves the list of headers that may be retrieved via the
     * <code>getHeader</code> method that will not return <code>null</code>. In
     * other words, this method returns all the headers that are available in
     * this object.
     * @see #getHeader
     * @return the array of headers that are set in this object or
     *         <code>null</code> if no headers are available
     */
    public int[] getHeaderList() {
        int[] res = new int[headerMap.size()];
        int idx = 0;
        for (Integer headerId : headerMap.keySet()) {
            res[idx] = headerId;
            idx++;
        };

        return res;
    }

    /**
     * Returns the response code received from the server. Response codes are
     * defined in the <code>ResponseCodes</code> class.
     * @see ResponseCodes
     * @return the response code retrieved from the server
     */
    public int getResponseCode() {
        return responseCode;
    }

    public String getResponseHexCode() {
        return Integer.toHexString(responseCode);
    }
}
