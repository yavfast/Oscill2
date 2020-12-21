/*
 * Copyright (C) 2015 The Android Open Source Project
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

import androidx.annotation.NonNull;
import androidx.annotation.Nullable;

import com.oscill.utils.IOUtils;
import com.oscill.utils.Log;

import java.io.ByteArrayOutputStream;
import java.io.IOException;
import java.security.MessageDigest;
import java.security.NoSuchAlgorithmException;

/**
 * This class defines a set of helper methods for the implementation of Obex.
 * @hide
 */
public final class ObexHelper {

    private static final String TAG = "ObexHelper";
    /**
     * Defines the basic packet length used by OBEX. Every OBEX packet has the
     * same basic format:<BR>
     * Byte 0: Request or Response Code Byte 1&2: Length of the packet.
     */
    public static final int BASE_PACKET_LENGTH = 3;

    /** Prevent object construction of helper class */
    private ObexHelper() {
    }

    /**
     * The maximum packet size for OBEX packets that this client can handle. At
     * present, this must be changed for each port. TODO: The max packet size
     * should be the Max incoming MTU minus TODO: L2CAP package headers and
     * RFCOMM package headers. TODO: Retrieve the max incoming MTU from TODO:
     * LocalDevice.getProperty().
     * NOTE: This value must be larger than or equal to the L2CAP SDU
     */
    /*
     * android note set as 0xFFFE to match remote MPS
     */
    public static final int MAX_PACKET_SIZE_INT = 0xFFFE;

    // The minimum allowed max packet size is 255 according to the OBEX specification
    public static final int LOWER_LIMIT_MAX_PACKET_SIZE = 255;

    // The length of OBEX Byte Sequency Header Id according to the OBEX specification
    public static final int OBEX_BYTE_SEQ_HEADER_LEN = 0x03;

    /**
     * Temporary workaround to be able to push files to Windows 7.
     * TODO: Should be removed as soon as Microsoft updates their driver.
     */
    public static final int MAX_CLIENT_PACKET_SIZE = 0xFC00;

    public static final int OBEX_OPCODE_FINAL_BIT_MASK = 0x80;

    public static final int OBEX_OPCODE_CONNECT = 0x80;

    public static final int OBEX_OPCODE_DISCONNECT = 0x81;

    public static final int OBEX_OPCODE_PUT = 0x02;

    public static final int OBEX_OPCODE_PUT_FINAL = 0x82;

    public static final int OBEX_OPCODE_GET = 0x03;

    public static final int OBEX_OPCODE_GET_FINAL = 0x83;

    public static final int OBEX_OPCODE_RESERVED = 0x04;

    public static final int OBEX_OPCODE_RESERVED_FINAL = 0x84;

    public static final int OBEX_OPCODE_SETPATH = 0x85;

    public static final int OBEX_OPCODE_ABORT = 0xFF;

    public static final int OBEX_AUTH_REALM_CHARSET_ASCII = 0x00;

    public static final int OBEX_AUTH_REALM_CHARSET_UNICODE = 0xFF;

    public static final byte OBEX_SRM_ENABLE         = 0x01; // For BT we only need enable/disable
    public static final byte OBEX_SRM_DISABLE        = 0x00;
    public static final byte OBEX_SRM_SUPPORT        = 0x02; // Unused for now

    public static final byte OBEX_SRMP_WAIT          = 0x01; // Only SRMP value used by BT

    /**
     * Updates the HeaderSet with the headers received in the byte array
     * provided. Invalid headers are ignored.
     * <P>
     * The first two bits of an OBEX Header specifies the type of object that is
     * being sent. The table below specifies the meaning of the high bits.
     * <TABLE>
     * <TR>
     * <TH>Bits 8 and 7</TH>
     * <TH>Value</TH>
     * <TH>Description</TH>
     * </TR>
     * <TR>
     * <TD>00</TD>
     * <TD>0x00</TD>
     * <TD>Null Terminated Unicode text, prefixed with 2 byte unsigned integer</TD>
     * </TR>
     * <TR>
     * <TD>01</TD>
     * <TD>0x40</TD>
     * <TD>Byte Sequence, length prefixed with 2 byte unsigned integer</TD>
     * </TR>
     * <TR>
     * <TD>10</TD>
     * <TD>0x80</TD>
     * <TD>1 byte quantity</TD>
     * </TR>
     * <TR>
     * <TD>11</TD>
     * <TD>0xC0</TD>
     * <TD>4 byte quantity - transmitted in network byte order (high byte first</TD>
     * </TR>
     * </TABLE>
     * This method uses the information in this table to determine the type of
     * Java object to create and passes that object with the full header to
     * setHeader() to update the HeaderSet object. Invalid headers will cause an
     * exception to be thrown. When it is thrown, it is ignored.
     * @param header the HeaderSet to update
     * @param headerArray the byte array containing headers
     * @throws IOException if an invalid header was found
     */
    public static void updateHeaderSet(@NonNull HeaderSet header, @NonNull byte[] headerArray) throws IOException {
        if (headerArray.length < OBEX_BYTE_SEQ_HEADER_LEN) {
            return;
        }

        byte[] data;

        int index = 0;
        while (index < headerArray.length) {
            int headerID = headerArray[index] & 0xFF;
            switch (headerID & 0xC0) {

                /*
                 * 0x00 is a unicode null terminate string with the first
                 * two bytes after the header identifier being the length
                 */
                case 0x00:
//                    header.setHeader(headerID, ObexHelper.convertToUnicode(data, true));
                    break;

                // Fall through
                /*
                 * 0x40 is a byte sequence with the first
                 * two bytes after the header identifier being the length
                 */
                case 0x40:
                    index++;
                    int length = convertToInt(new byte[]{headerArray[index], headerArray[index + 1]});
                    index += 2;
                    length -= OBEX_BYTE_SEQ_HEADER_LEN;
                    data = new byte[length];
                    System.arraycopy(headerArray, index, data, 0, length);

                    header.setHeader(headerID, data);

                    index += length;
                    break;

                /*
                 * 0x80 is a byte header.  The only valid byte headers are
                 * the 16 user defined byte headers.
                 */
                case 0x80:
                    index++;
                    data = new byte[]{headerArray[index]};
                    header.setHeader(headerID, data);
                    index++;
                    break;

                /*
                 * 0xC0 is a 4 byte unsigned integer header and with the
                 * exception of TIME_4_BYTE will be converted to a Long
                 * and added.
                 */
                case 0xC0:
                    index++;
                    data = new byte[4];
                    System.arraycopy(headerArray, index, data, 0, 4);
                    header.setHeader(headerID, data);
                    index += 4;
                    break;
            }

        }
    }

    /**
     * Creates the header part of OBEX packet based on the header provided.
     * TODO: Could use getHeaderList() to get the array of headers to include
     * and then use the high two bits to determine the the type of the object
     * and construct the byte array from that. This will make the size smaller.
     * @param head the header used to construct the byte array
     * @param nullOut <code>true</code> if the header should be set to
     *        <code>null</code> once it is added to the array or
     *        <code>false</code> if it should not be nulled out
     * @return the header of an OBEX packet
     */
    @NonNull
    public static byte[] createHeader(@NonNull HeaderSet head, boolean nullOut) {
        ByteArrayOutputStream out = new ByteArrayOutputStream();
        try {
            for (int headerId : head.getHeaderList()) {
                Object headerValue = head.getHeader(headerId);
                if (headerValue != null) {
                    byte[] value = null;
                    Class<?> valueClass = headerValue.getClass();
                    if (valueClass == byte[].class) {
                        value = (byte[]) headerValue;

                    } else if (valueClass == String.class) {
                        value = ObexHelper.convertToUnicodeByteArray((String)headerValue);

                    } else if (valueClass == Long.class) {
                        value = ObexHelper.convertToByteArray((Long) headerValue);

                    } else if (valueClass == Byte.class) {
                        value = new byte[1];
                        value[0] = (Byte) headerValue;
                    }

                    if (value != null) {
                        out.write((byte) headerId);
                        switch (headerId) {
                            case Header.OSCILL_1BYTE:
                            case Header.OSCILL_2BYTE:
                            case Header.OSCILL_4BYTE:
                            case Header.OSCILL_CRC:
                                // Skip length part
                                break;

                            default:
                                int length = value.length + 3;
                                byte[] lengthArray = new byte[2];
                                lengthArray[0] = (byte) (255 & (length >> 8));
                                lengthArray[1] = (byte) (255 & length);
                                out.write(lengthArray);
                        }
                        out.write(value);
                    } else {
                        throw new IllegalArgumentException("Bad headerValue: " + headerValue.getClass());
                    }

                    if (nullOut) {
                        head.setHeader(headerId, null);
                    }
                }
            }

            return out.toByteArray();
        } catch (IOException e) {
            Log.e(TAG, e);
        } finally {
            IOUtils.close(out);
        }

        throw new IllegalStateException();
    }

    /**
     * Determines where the maximum divide is between headers. This method is
     * used by put and get operations to separate headers to a size that meets
     * the max packet size allowed.
     * @param headerArray the headers to separate
     * @param start the starting index to search
     * @param maxSize the maximum size of a packet
     * @return the index of the end of the header block to send or -1 if the
     *         header could not be divided because the header is too large
     */
    public static int findHeaderEnd(byte[] headerArray, int start, int maxSize) {
        int fullLength = 0;
        int lastLength = -1;
        int index = start;
        int length = 0;

        while ((fullLength < maxSize) && (index < headerArray.length)) {
            int headerID = (headerArray[index] < 0 ? headerArray[index] + 256 : headerArray[index]);
            lastLength = fullLength;

            switch (headerID & (0xC0)) {

                case 0x00:
                    // Fall through
                case 0x40:

                    index++;
                    length = (headerArray[index] < 0 ? headerArray[index] + 256
                            : headerArray[index]);
                    length = length << 8;
                    index++;
                    length += (headerArray[index] < 0 ? headerArray[index] + 256
                            : headerArray[index]);
                    length -= 3;
                    index++;
                    index += length;
                    fullLength += length + 3;
                    break;

                case 0x80:

                    index++;
                    index++;
                    fullLength += 2;
                    break;

                case 0xC0:

                    index += 5;
                    fullLength += 5;
                    break;

            }

        }

        /*
         * Determine if this is the last header or not
         */
        if (lastLength == 0) {
            /*
             * Since this is the last header, check to see if the size of this
             * header is less then maxSize.  If it is, return the length of the
             * header, otherwise return -1.  The length of the header is
             * returned since it would be the start of the next header
             */
            if (fullLength < maxSize) {
                return headerArray.length;
            } else {
                return -1;
            }
        } else {
            return lastLength + start;
        }
    }

    @NonNull
    public static String convertToString(@NonNull byte[] data) {
        return new String(data);
    }
    /**
     * Converts the byte array to a int.
     * @param data the byte array to convert to a long
     * @return the byte array as a int
     */
    public static int convertToInt(@NonNull byte[] data) {
        int result = 0;
        int value;
        int power = 0;

        for (int i = (data.length - 1); i >= 0; i--) {
            value = data[i] & 0xFF;
            result |= value << power;
            power += 8;
        }

        return result;
    }

    /**
     * Converts the int to a 4 byte array. The int must be non negative.
     * @param l the int to convert
     * @return a byte array that is the same as the long
     */
    public static byte[] convertToByteArray(long l) {
        byte[] b = new byte[4];

        b[0] = (byte)(255 & (l >> 24));
        b[1] = (byte)(255 & (l >> 16));
        b[2] = (byte)(255 & (l >> 8));
        b[3] = (byte)(255 & l);

        return b;
    }

    public static byte[] convertToByteArray(int value) {
        byte[] b = new byte[4];

        b[0] = (byte)(255 & (value >> 24));
        b[1] = (byte)(255 & (value >> 16));
        b[2] = (byte)(255 & (value >> 8));
        b[3] = (byte)(255 & value);

        return b;
    }
    /**
     * Converts the String to a UNICODE byte array. It will also add the ending
     * null characters to the end of the string.
     * @param s the string to convert
     * @return the unicode byte array of the string
     */
    public static byte[] convertToUnicodeByteArray(String s) {
        if (s == null) {
            return null;
        }

        char c[] = s.toCharArray();
        byte[] result = new byte[(c.length * 2) + 2];
        for (int i = 0; i < c.length; i++) {
            result[(i * 2)] = (byte)(c[i] >> 8);
            result[((i * 2) + 1)] = (byte)c[i];
        }

        // Add the UNICODE null character
        result[result.length - 2] = 0;
        result[result.length - 1] = 0;

        return result;
    }

    /**
     * Retrieves the value from the byte array for the tag value specified. The
     * array should be of the form Tag - Length - Value triplet.
     * @param tag the tag to retrieve from the byte array
     * @param triplet the byte sequence containing the tag length value form
     * @return the value of the specified tag
     */
    public static byte[] getTagValue(byte tag, byte[] triplet) {

        int index = findTag(tag, triplet);
        if (index == -1) {
            return null;
        }

        index++;
        int length = triplet[index] & 0xFF;

        byte[] result = new byte[length];
        index++;
        System.arraycopy(triplet, index, result, 0, length);

        return result;
    }

    /**
     * Finds the index that starts the tag value pair in the byte array provide.
     * @param tag the tag to look for
     * @param value the byte array to search
     * @return the starting index of the tag or -1 if the tag could not be found
     */
    public static int findTag(byte tag, byte[] value) {
        int length = 0;

        if (value == null) {
            return -1;
        }

        int index = 0;

        while ((index < value.length) && (value[index] != tag)) {
            length = value[index + 1] & 0xFF;
            index += length + 2;
        }

        if (index >= value.length) {
            return -1;
        }

        return index;
    }

    /**
     * Converts the byte array provided to a unicode string.
     * @param data the byte array to convert to a string
     * @param includesNull determine if the byte string provided contains the
     *        UNICODE null character at the end or not; if it does, it will be
     *        removed
     * @return a Unicode string
     * @throws IllegalArgumentException if the byte array has an odd length
     */
    @Nullable
    public static String convertToUnicode(@Nullable byte[] data, boolean includesNull) {
        if (data == null || data.length == 0) {
            return null;
        }
        int arrayLength = data.length;
        if (!((arrayLength % 2) == 0)) {
            throw new IllegalArgumentException("Byte array not of a valid form");
        }
        arrayLength = (arrayLength >> 1);
        if (includesNull) {
            arrayLength -= 1;
        }

        char[] c = new char[arrayLength];
        for (int i = 0; i < arrayLength; i++) {
            int upper = data[2 * i];
            int lower = data[(2 * i) + 1];
            if (upper < 0) {
                upper += 256;
            }
            if (lower < 0) {
                lower += 256;
            }
            // If upper and lower both equal 0, it should be the end of string.
            // Ignore left bytes from array to avoid potential issues
            if (upper == 0 && lower == 0) {
                return new String(c, 0, i);
            }

            c[i] = (char)((upper << 8) | lower);
        }

        return new String(c);
    }

    /**
     * Compute the MD5 hash of the byte array provided. Does not accumulate
     * input.
     * @param in the byte array to hash
     * @return the MD5 hash of the byte array
     */
    public static byte[] computeMd5Hash(byte[] in) {
        try {
            MessageDigest md5 = MessageDigest.getInstance("MD5");
            return md5.digest(in);
        } catch (NoSuchAlgorithmException e) {
            throw new RuntimeException(e);
        }
    }

    /**
     * Computes an authentication challenge header.
     * @param nonce the challenge that will be provided to the peer; the
     *        challenge must be 16 bytes long
     * @param realm a short description that describes what password to use
     * @param access if <code>true</code> then full access will be granted if
     *        successful; if <code>false</code> then read only access will be
     *        granted if successful
     * @param userID if <code>true</code>, a user ID is required in the reply;
     *        if <code>false</code>, no user ID is required
     * @throws IllegalArgumentException if the challenge is not 16 bytes long;
     *         if the realm can not be encoded in less then 255 bytes
     * @throws IOException if the encoding scheme ISO 8859-1 is not supported
     */
    public static byte[] computeAuthenticationChallenge(byte[] nonce, String realm, boolean access,
            boolean userID) throws IOException {
        byte[] authChall = null;

        if (nonce.length != 16) {
            throw new IllegalArgumentException("Nonce must be 16 bytes long");
        }

        /*
         * The authentication challenge is a byte sequence of the following form
         * byte 0: 0x00 - the tag for the challenge
         * byte 1: 0x10 - the length of the challenge; must be 16
         * byte 2-17: the authentication challenge
         * byte 18: 0x01 - the options tag; this is optional in the spec, but
         *                 we are going to include it in every message
         * byte 19: 0x01 - length of the options; must be 1
         * byte 20: the value of the options; bit 0 is set if user ID is
         *          required; bit 1 is set if access mode is read only
         * byte 21: 0x02 - the tag for authentication realm; only included if
         *                 an authentication realm is specified
         * byte 22: the length of the authentication realm; only included if
         *          the authentication realm is specified
         * byte 23: the encoding scheme of the authentication realm; we will use
         *          the ISO 8859-1 encoding scheme since it is part of the KVM
         * byte 24 & up: the realm if one is specified.
         */
        if (realm == null) {
            authChall = new byte[21];
        } else {
            if (realm.length() >= 255) {
                throw new IllegalArgumentException("Realm must be less then 255 bytes");
            }
            authChall = new byte[24 + realm.length()];
            authChall[21] = 0x02;
            authChall[22] = (byte)(realm.length() + 1);
            authChall[23] = 0x01; // ISO 8859-1 Encoding
            System.arraycopy(realm.getBytes("ISO8859_1"), 0, authChall, 24, realm.length());
        }

        // Include the nonce field in the header
        authChall[0] = 0x00;
        authChall[1] = 0x10;
        System.arraycopy(nonce, 0, authChall, 2, 16);

        // Include the options header
        authChall[18] = 0x01;
        authChall[19] = 0x01;
        authChall[20] = 0x00;

        if (!access) {
            authChall[20] = (byte)(authChall[20] | 0x02);
        }
        if (userID) {
            authChall[20] = (byte)(authChall[20] | 0x01);
        }

        return authChall;
    }

}
