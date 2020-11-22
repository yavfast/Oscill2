package com.oscill.obex;

public interface Header {
    /**
     * Represents the OBEX Count header. This allows the connection statement to
     * tell the server how many objects it plans to send or retrieve.
     * <P>
     * The value of <code>COUNT</code> is 0xC0 (192).
     */
    int COUNT = 0xC0;
    /**
     * Represents the OBEX Name header. This specifies the name of the object.
     * <P>
     * The value of <code>NAME</code> is 0x01 (1).
     */
    int NAME = 0x01;
    /**
     * Represents the OBEX Type header. This allows a request to specify the
     * type of the object (e.g. text, html, binary, etc.).
     * <P>
     * The value of <code>TYPE</code> is 0x42 (66).
     */
    int TYPE = 0x42;
    /**
     * Represents the OBEX Length header. This is the length of the object in
     * bytes.
     * <P>
     * The value of <code>LENGTH</code> is 0xC3 (195).
     */
    int LENGTH = 0xC3;
    /**
     * Represents the OBEX Time header using the ISO 8601 standards. This is the
     * preferred time header.
     * <P>
     * The value of <code>TIME_ISO_8601</code> is 0x44 (68).
     */
    int TIME_ISO_8601 = 0x44;
    /**
     * Represents the OBEX Time header using the 4 byte representation. This is
     * only included for backwards compatibility. It represents the number of
     * seconds since January 1, 1970.
     * <P>
     * The value of <code>TIME_4_BYTE</code> is 0xC4 (196).
     */
    int TIME_4_BYTE = 0xC4;
    /**
     * Represents the OBEX Description header. This is a text description of the
     * object.
     * <P>
     * The value of <code>DESCRIPTION</code> is 0x05 (5).
     */
    int DESCRIPTION = 0x05;
    /**
     * Represents the OBEX Target header. This is the name of the service an
     * operation is targeted to.
     * <P>
     * The value of <code>TARGET</code> is 0x46 (70).
     */
    int TARGET = 0x46;
    /**
     * Represents the OBEX HTTP header. This allows an HTTP 1.X header to be
     * included in a request or reply.
     * <P>
     * The value of <code>HTTP</code> is 0x47 (71).
     */
    int HTTP = 0x47;
    /**
     * Represents the OBEX BODY header.
     * <P>
     * The value of <code>BODY</code> is 0x48 (72).
     */
    int BODY = 0x48;
    /**
     * Represents the OBEX End of BODY header.
     * <P>
     * The value of <code>BODY</code> is 0x49 (73).
     */
    int END_OF_BODY = 0x49;
    /**
     * Represents the OBEX Who header. Identifies the OBEX application to
     * determine if the two peers are talking to each other.
     * <P>
     * The value of <code>WHO</code> is 0x4A (74).
     */
    int WHO = 0x4A;
    /**
     * Represents the OBEX Connection ID header. Identifies used for OBEX
     * connection multiplexing.
     * <P>
     * The value of <code>CONNECTION_ID</code> is 0xCB (203).
     */

    int CONNECTION_ID = 0xCB;
    /**
     * Represents the OBEX Application Parameter header. This header specifies
     * additional application request and response information.
     * <P>
     * The value of <code>APPLICATION_PARAMETER</code> is 0x4C (76).
     */
    int APPLICATION_PARAMETER = 0x4C;
    /**
     * Represents the OBEX authentication digest-challenge.
     * <P>
     * The value of <code>AUTH_CHALLENGE</code> is 0x4D (77).
     */
    int AUTH_CHALLENGE = 0x4D;
    /**
     * Represents the OBEX authentication digest-response.
     * <P>
     * The value of <code>AUTH_RESPONSE</code> is 0x4E (78).
     */
    int AUTH_RESPONSE = 0x4E;
    /**
     * Represents the OBEX Object Class header. This header specifies the OBEX
     * object class of the object.
     * <P>
     * The value of <code>OBJECT_CLASS</code> is 0x4F (79).
     */
    int OBJECT_CLASS = 0x4F;
    /**
     * Represents the OBEX Single Response Mode (SRM). This header is used
     * for Single response mode, introduced in OBEX 1.5.
     * <P>
     * The value of <code>SINGLE_RESPONSE_MODE</code> is 0x97 (151).
     */
    int SINGLE_RESPONSE_MODE = 0x97;
    /**
     * Represents the OBEX Single Response Mode Parameters. This header is used
     * for Single response mode, introduced in OBEX 1.5.
     * <P>
     * The value of <code>SINGLE_RESPONSE_MODE_PARAMETER</code> is 0x98 (152).
     */
    int SINGLE_RESPONSE_MODE_PARAMETER = 0x98;
    int OSCILL_PROPERTY = 0x70;
    int OSCILL_REGISTRY = 0x71;
    int OSCILL_DATA = 0x72;
    int OSCILL_CRC = 0xB0;
    int OSCILL_1BYTE = 0xB1;
    int OSCILL_2BYTE = 0xF0;
    int OSCILL_4BYTE = 0xF1;
    int OSCILL_EMPTY = 0x00;
}
