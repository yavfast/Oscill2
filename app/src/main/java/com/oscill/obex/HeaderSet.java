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

import androidx.annotation.Nullable;

import java.io.IOException;
import java.util.LinkedHashMap;
import java.util.Map;

/**
 * This class implements the com.oscill.obex.HeaderSet interface for OBEX over
 * RFCOMM or OBEX over l2cap.
 * @hide
 */
public final class HeaderSet {

    private final Map<Integer,byte[]> headerMap = new LinkedHashMap<>();
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
