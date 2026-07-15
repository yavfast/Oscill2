/* Reference C8051F340 firmware — realistic OSCILLOSCOPE structure (SDCC).
 * NOT functional hardware firmware: a STRUCTURE reference whose code+data layout
 * mirrors the Oscill .ofw plaintext (vector table, ADC path, OBEX register table,
 * calibration 8-byte records, USB descriptors, LUTs, ASCII cribs) so a future
 * decrypt can be recognised/validated. See STRUCTURE.md and the mask spike.
 * Register names + OBEX codes are the project's real ones (skills/obex_protocol,
 * web_oscill/oscill_client.py). */
#include <C8051F340.h>

/* ---- OBEX protocol constants (from oscill_client.py) ---- */
#define OSCILL_PROPERTY 0x70
#define OSCILL_REGISTRY 0x71
#define OSCILL_DATA     0x72
#define OSCILL_1BYTE    0xB1
#define OSCILL_2BYTE    0xF0
#define OSCILL_4BYTE    0xF1

#define NSAMP 512
#define NRANGE 8

/* ================= const / CODE data (populates data pages) ================= */

/* Banner + identity cribs — same shapes the device reports over OBEX. */
__code const char banner[]  = "Oscill.com oscilloscope\r\n";
__code const char dev_name[] = "Uosc";
__code const char fw_ver[]   = "1.26";
__code const char hw_ver[]   = "1.2";

/* OBEX register table: {name, value type, backing address}. Real register names. */
typedef struct { char name[4]; unsigned char type; unsigned int addr; } reg_t;
__code const reg_t reg_table[] = {
    {"VSW", OSCILL_2BYTE, 0x0100},   /* software version */
    {"VSN", OSCILL_4BYTE, 0x0102},   /* serial number    */
    {"VNM", OSCILL_2BYTE, 0x0106},   /* device name code */
    {"VHW", OSCILL_2BYTE, 0x0108},   /* hardware version */
    {"QS",  OSCILL_2BYTE, 0x010A},   /* sample count     */
    {"TS",  OSCILL_2BYTE, 0x010C},   /* time scale       */
    {"RS",  OSCILL_2BYTE, 0x010E},   /* range scale      */
    {"M1",  OSCILL_1BYTE, 0x0110},   /* mode select      */
    {"O1",  OSCILL_1BYTE, 0x0111},   /* offset control   */
    {"AP",  OSCILL_2BYTE, 0x0112},   /* aperture         */
    {"RT",  OSCILL_1BYTE, 0x0114},   /* run/trigger      */
    {"AVG", OSCILL_1BYTE, 0x0115},   /* averaging        */
};
#define NREG (sizeof(reg_table)/sizeof(reg_table[0]))

/* ADC calibration table: one 8-byte record per input range.
 * Layout {gain_lo,gain_hi, off_lo,off_hi, RESERVED=0xFF, flags, rangecode, xsum}
 * — deliberately 0xFF at offset 4, mirroring the vendor 'ff@lat' stride-8 lattice. */
__code const unsigned char cal_table[NRANGE][8] = {
    {0x00,0x04, 0x00,0x00, 0xFF, 0x01, 0x00, 0x05},  /* x1    */
    {0x9A,0x03, 0x10,0x00, 0xFF, 0x01, 0x01, 0xA5},  /* x2    */
    {0x40,0x03, 0x20,0x00, 0xFF, 0x01, 0x02, 0x56},  /* x5    */
    {0x00,0x02, 0x28,0x00, 0xFF, 0x02, 0x03, 0x2D},  /* x10   */
    {0xCD,0x01, 0x30,0x00, 0xFF, 0x02, 0x04, 0x04},  /* x20   */
    {0x00,0x01, 0x38,0x00, 0xFF, 0x02, 0x05, 0x40},  /* x50   */
    {0x80,0x00, 0x40,0x00, 0xFF, 0x04, 0x06, 0xCA},  /* x100  */
    {0x40,0x00, 0x48,0x00, 0xFF, 0x04, 0x07, 0x93},  /* x200  */
};

/* Hex-encode LUT (samples -> ASCII hex for HTTP/OBEX transport). */
__code const char hexlut[] = "0123456789ABCDEF";

/* Full sine LUT (256 entries) — timebase test signal / display helper. */
__code const unsigned char sine_lut[256] = {
128,131,134,137,140,143,146,149,152,156,159,162,165,168,171,174,
176,179,182,185,188,191,193,196,199,201,204,206,209,211,213,216,
218,220,222,224,226,228,230,232,234,236,237,239,240,242,243,245,
246,247,248,249,250,251,252,252,253,254,254,255,255,255,255,255,
255,255,255,255,255,255,254,254,253,252,252,251,250,249,248,247,
246,245,243,242,240,239,237,236,234,232,230,228,226,224,222,220,
218,216,213,211,209,206,204,201,199,196,193,191,188,185,182,179,
176,174,171,168,165,162,159,156,152,149,146,143,140,137,134,131,
128,124,121,118,115,112,109,106,103, 99, 96, 93, 90, 87, 84, 81,
 79, 76, 73, 70, 67, 64, 62, 59, 56, 54, 51, 49, 46, 44, 42, 39,
 37, 35, 33, 31, 29, 27, 25, 23, 21, 19, 18, 16, 15, 13, 12, 10,
  9,  8,  7,  6,  5,  4,  3,  3,  2,  1,  1,  0,  0,  0,  0,  0,
  0,  0,  0,  0,  0,  0,  1,  1,  2,  3,  3,  4,  5,  6,  7,  8,
  9, 10, 12, 13, 15, 16, 18, 19, 21, 23, 25, 27, 29, 31, 33, 35,
 37, 39, 42, 44, 46, 49, 51, 54, 56, 59, 62, 64, 67, 70, 73, 76,
 79, 81, 84, 87, 90, 93, 96, 99,103,106,109,112,115,118,121,124,
};

/* USB device + configuration descriptor (SiLabs USBXpress-style block). */
__code const unsigned char usb_desc[] = {
    0x12,0x01,0x00,0x02,0x00,0x00,0x00,0x40,  /* device: bLength,type,bcdUSB,class,maxpkt */
    0xC4,0x10,0x07,0xEA,0x00,0x01,0x01,0x02,  /* idVendor 10C4 (SiLabs), idProduct EA07  */
    0x03,0x01,
    0x09,0x02,0x20,0x00,0x01,0x01,0x00,0x80,0x32, /* config: total,ifaces,attr,maxpower */
    0x09,0x04,0x00,0x00,0x02,0xFF,0x00,0x00,0x00, /* interface: vendor class */
    0x07,0x05,0x81,0x02,0x40,0x00,0x00,           /* EP1 IN bulk  */
    0x07,0x05,0x01,0x02,0x40,0x00,0x00,           /* EP1 OUT bulk */
};

/* ================= XDATA (RAM) — sample + output buffers ================= */
__xdata unsigned char  sample_buf[NSAMP];   /* raw ADC samples          */
__xdata unsigned char  hex_out[128];        /* hex-encoded output chunk */
__xdata volatile unsigned int  wr_idx;      /* sample write cursor      */
__xdata unsigned int   sw_version = 0x011A; /* 1.26 -> reported via VSW */
__xdata unsigned char  cur_range, cur_mode, run_flag;

volatile __bit adc_ready;
volatile unsigned char tick;

/* ================= interrupt handlers (populate the vector table) ======= */
void ext0_isr(void)   __interrupt(0)  { run_flag ^= 1; }              /* /INT0    */
void timer0_isr(void) __interrupt(1)  { tick++; TH0 = 0x3C; }         /* timebase */
void uart0_isr(void)  __interrupt(4)  { if (RI0) RI0 = 0; }           /* OBEX I/O */
void timer2_isr(void) __interrupt(5)  { TF2H = 0; }                   /* sweep    */
void usb0_isr(void)   __interrupt(8)  { USB0ADR = 0x00; }             /* USBXpress */
void adc0_isr(void)   __interrupt(10) {                               /* ADC EOC  */
    AD0INT = 0;
    if (wr_idx < NSAMP) sample_buf[wr_idx++] = ADC0H;
    if (wr_idx >= NSAMP) adc_ready = 1;
}
void pca0_isr(void)   __interrupt(11) { CF = 0; }                     /* PWM/PCA  */

/* ================= signal-processing helpers (real code shapes) ========= */

/* ADC code -> millivolts using the range's calibration record (integer math). */
static int adc_to_mv(unsigned char code, unsigned char range) {
    unsigned int gain = cal_table[range][0] | ((unsigned int)cal_table[range][1] << 8);
    int off = cal_table[range][2] | ((int)cal_table[range][3] << 8);
    long mv = ((long)code * gain) >> 8;
    return (int)(mv - off);
}

/* Segment-based frequency estimate (project algorithm, NOT FFT):
 * count threshold-crossing segments across the sample window. */
static unsigned int detect_segments(unsigned char threshold) {
    unsigned int i, segs = 0;
    unsigned char prev = 0, cur;
    for (i = 0; i < NSAMP; i++) {
        cur = (sample_buf[i] > threshold) ? 1 : 0;
        if (cur && !prev) segs++;
        prev = cur;
    }
    return segs;
}

/* Hex-encode n samples into hex_out (2 chars/byte) for OBEX/HTTP transport. */
static unsigned char hex_encode(unsigned char n) {
    unsigned char i, o = 0, v;
    for (i = 0; i < n && o < 126; i++) {
        v = sample_buf[i];
        hex_out[o++] = hexlut[v >> 4];
        hex_out[o++] = hexlut[v & 0x0F];
    }
    return o;
}

/* Two-char register-name compare against the OBEX table -> table index or 0xFF. */
static unsigned char reg_lookup(char c0, char c1) {
    unsigned char i;
    for (i = 0; i < NREG; i++)
        if (reg_table[i].name[0] == c0 && reg_table[i].name[1] == c1)
            return i;
    return 0xFF;
}

/* OBEX property dispatch: given a 2-char register name, return its value word. */
static unsigned int obex_get(char c0, char c1) {
    unsigned char idx = reg_lookup(c0, c1);
    if (idx == 0xFF) return 0xFFFF;
    switch (idx) {
        case 0: return sw_version;               /* VSW */
        case 4: return wr_idx;                    /* QS  */
        case 7: return cur_mode;                  /* M1  */
        default: return reg_table[idx].addr;
    }
}

/* ================= peripheral init + main loop ========================== */
static void hw_init(void) {
    PCA0MD &= ~0x40;              /* disable watchdog                        */
    OSCICN  = 0x83;              /* internal osc / 1                        */
    CLKSEL  = 0x00;
    AMX0P   = 0x00;             /* ADC positive input = P2.0               */
    ADC0CF  = 0xF8;            /* SAR clock + gain                        */
    ADC0CN  = 0x82;           /* ADC on, convert on Timer2 overflow      */
    TMOD    = 0x21;          /* T1 8-bit auto (baud), T0 16-bit         */
    CKCON  |= 0x08;
    TH1     = 0x96;         /* ~115200 @ 24MHz                         */
    SCON0   = 0x10;        /* UART rx enable                          */
    TR1     = 1;
    TMR2RLL = 0x00; TMR2RLH = 0xF0; TMR2CN = 0x04;  /* sweep timer     */
    P2MDOUT = 0x04;
    IE      = 0x92;       /* EA + ET0 + ES0                          */
    EIE1    = 0x08;      /* enable ADC0 EOC irq                     */
    run_flag = 1; cur_range = 3;
}

void main(void) {
    unsigned int freq; int mv; unsigned char nhex;
    hw_init();
    wr_idx = 0;
    for (;;) {
        if (adc_ready) {
            adc_ready = 0;
            freq = detect_segments(128);           /* segment freq detect  */
            mv   = adc_to_mv(sample_buf[0], cur_range);
            nhex = hex_encode(64);                  /* pack for transport   */
            sw_version = (unsigned int)freq ^ (unsigned int)mv ^ nhex;
            wr_idx = 0;                             /* restart acquisition  */
        }
        if (RI0) {                                  /* OBEX request pending */
            char a = SBUF0; while (!RI0); RI0 = 0;
            { char b = SBUF0; RI0 = 0;
              SBUF0 = (char)(obex_get(a, b) & 0xFF); }
        }
        P2 = tick ^ sine_lut[tick];
    }
}
