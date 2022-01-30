package math.fft;

import androidx.annotation.NonNull;

public class Fourier {

    private final Bluestein bluestein;

    public Fourier() {
        bluestein = new Bluestein();
    }

    @NonNull
    public ComplexArray forwardDFT(@NonNull ComplexArray array) {
        int N = array.length();
        if (N <= 1) {
            return array.copy();
        }

        if (isPowerOfTwo(N)) {
            return forwardDFT_pow2(array);
        }

        return bluestein.forwardDFT(array);
    }

    @NonNull
    static ComplexArray forwardDFT_pow2(@NonNull ComplexArray array) {
        ComplexArray res = array.copy();

        final int N = array.length();
        if (N <= 1) {
            return res;
        }

        if (N == 2) {
            float[] dataR = res.re();
            float[] dataI = res.im();
            float srcR0 = dataR[0];
            float srcI0 = dataI[0];
            dataR[0] = srcR0 + dataR[1];
            dataR[1] = srcR0 - dataR[1];
            dataI[0] = srcI0 + dataI[1];
            dataI[1] = srcI0 - dataI[1];
            return res;
        }

        bitReversalShuffle(res);
        fourTermForward(res);
        combineEvenOdd(res, false);
        postProcess(res, false);

        return res;
    }

    @NonNull
    public ComplexArray inverseDFT(@NonNull ComplexArray freqs) {
        final int N = freqs.length();
        if (N <= 1) {
            return freqs.copy();
        }

        if (isPowerOfTwo(N)) {
            return inverseDFT_pow2(freqs);
        }

        return bluestein.inverseDFT(freqs);
    }

    @NonNull
    static ComplexArray inverseDFT_pow2(@NonNull ComplexArray freqs) {
        ComplexArray res = freqs.copy();
        final int N = freqs.length();
        if (N <= 1) {
            return res;
        }

        if (N == 2) {
            float[] dataR = res.re();
            float[] dataI = res.im();
            float srcR0 = dataR[0];
            float srcI0 = dataI[0];
            float srcR1 = dataR[1];
            float srcI1 = dataI[1];
            float scaleFactor = (1.0f / N);
            // X_0 = x_0 + x_1
            dataR[0] = srcR0 + srcR1;
            dataR[0] *= scaleFactor;
            dataI[0] = srcI0 + srcI1;
            dataI[0] *= scaleFactor;
            // X_1 = x_0 - x_1
            dataR[1] = srcR0 - srcR1;
            dataR[1] *= scaleFactor;
            dataI[1] = srcI0 - srcI1;
            dataI[1] *= scaleFactor;
            return res;
        }

        bitReversalShuffle(res);
        fourTermInverse(res);
        combineEvenOdd(res, true);
        postProcess(res, true);

        return res;
    }

    private static void fourTermForward(@NonNull ComplexArray array) {
        float[] dataR = array.re();
        float[] dataI = array.im();
        int n = array.length();

        int i1, i2, i3;
        float srcR0, srcI0, srcR1, srcI1, srcR2, srcI2, srcR3, srcI3;

        for (int i0 = 0; i0 < n; i0 += 4) {
            i1 = i0 + 1;
            i2 = i0 + 2;
            i3 = i0 + 3;

            srcR0 = dataR[i0];
            srcI0 = dataI[i0];
            srcR1 = dataR[i2];
            srcI1 = dataI[i2];
            srcR2 = dataR[i1];
            srcI2 = dataI[i1];
            srcR3 = dataR[i3];
            srcI3 = dataI[i3];

            // 4-term DFT
            // X_0 = x_0 + x_1 + x_2 + x_3
            dataR[i0] = srcR0 + srcR1 + srcR2 + srcR3;
            dataI[i0] = srcI0 + srcI1 + srcI2 + srcI3;
            // X_1 = x_0 - x_2 + j * (x_3 - x_1)
            dataR[i1] = srcR0 - srcR2 + (srcI1 - srcI3);
            dataI[i1] = srcI0 - srcI2 + (srcR3 - srcR1);
            // X_2 = x_0 - x_1 + x_2 - x_3
            dataR[i2] = srcR0 - srcR1 + srcR2 - srcR3;
            dataI[i2] = srcI0 - srcI1 + srcI2 - srcI3;
            // X_3 = x_0 - x_2 + j * (x_1 - x_3)
            dataR[i3] = srcR0 - srcR2 + (srcI3 - srcI1);
            dataI[i3] = srcI0 - srcI2 + (srcR1 - srcR3);
        }
    }

    private static void fourTermInverse(@NonNull ComplexArray array) {
        float[] dataR = array.re();
        float[] dataI = array.im();
        int n = array.length();

        float srcR0, srcI0, srcR1, srcI1, srcR2, srcI2, srcR3, srcI3;
        int i0, i1, i2, i3;

        for (i0 = 0; i0 < n; i0 += 4) {
            i1 = i0 + 1;
            i2 = i0 + 2;
            i3 = i0 + 3;

            srcR0 = dataR[i0];
            srcI0 = dataI[i0];
            srcR1 = dataR[i2];
            srcI1 = dataI[i2];
            srcR2 = dataR[i1];
            srcI2 = dataI[i1];
            srcR3 = dataR[i3];
            srcI3 = dataI[i3];

            // 4-term DFT
            // X_0 = x_0 + x_1 + x_2 + x_3
            dataR[i0] = srcR0 + srcR1 + srcR2 + srcR3;
            dataI[i0] = srcI0 + srcI1 + srcI2 + srcI3;
            // X_1 = x_0 - x_2 + j * (x_3 - x_1)
            dataR[i1] = srcR0 - srcR2 + (srcI3 - srcI1);
            dataI[i1] = srcI0 - srcI2 + (srcR1 - srcR3);
            // X_2 = x_0 - x_1 + x_2 - x_3
            dataR[i2] = srcR0 - srcR1 + srcR2 - srcR3;
            dataI[i2] = srcI0 - srcI1 + srcI2 - srcI3;
            // X_3 = x_0 - x_2 + j * (x_1 - x_3)
            dataR[i3] = srcR0 - srcR2 + (srcI1 - srcI3);
            dataI[i3] = srcI0 - srcI2 + (srcR3 - srcR1);
        }
    }

    private static void combineEvenOdd(@NonNull ComplexArray array, boolean doInverse) {
        float[] dataR = array.re();
        float[] dataI = array.im();
        int n = array.length();

        int n0, logN0, destEvenStartIndex, destOddStartIndex, r, destEvenStartIndex_r, destOddStartIndex_r;
        float wSubN0R, wSubN0I, wSubN0ToRR, wSubN0ToRI;
        float grR, grI, hrR, hrI, nextWsubN0ToRR, nextWsubN0ToRI;
        float wSubN0ToRR_hrR, wSubN0ToRR_hrI, wSubN0ToRI_hrR, wSubN0ToRI_hrI;

        int lastN0 = 4;
        int lastLogN0 = 2;
        while (lastN0 < n) {
            n0 = lastN0 << 1;
            logN0 = lastLogN0 + 1;
            wSubN0R = W_SUB_N_R[logN0];
            wSubN0I = doInverse ? -W_SUB_N_I[logN0] : W_SUB_N_I[logN0];

            // Combine even/odd transforms of size lastN0 into a transform of
            // size N0 (lastN0 * 2).
            for (destEvenStartIndex = 0; destEvenStartIndex < n; destEvenStartIndex += n0) {
                destOddStartIndex = destEvenStartIndex + lastN0;

                wSubN0ToRR = 1;
                wSubN0ToRI = 0;

                for (r = 0; r < lastN0; r++) {
                    destEvenStartIndex_r = destEvenStartIndex + r;
                    destOddStartIndex_r = destOddStartIndex + r;

                    grR = dataR[destEvenStartIndex_r];
                    hrR = dataR[destOddStartIndex_r];
                    grI = dataI[destEvenStartIndex_r];
                    hrI = dataI[destOddStartIndex_r];

                    // dest[destEvenStartIndex + r] = Gr + WsubN0ToR * Hr
                    // dest[destOddStartIndex + r] = Gr - WsubN0ToR * Hr

                    wSubN0ToRR_hrR = wSubN0ToRR * hrR;
                    wSubN0ToRR_hrI = wSubN0ToRR * hrI;
                    wSubN0ToRI_hrR = wSubN0ToRI * hrR;
                    wSubN0ToRI_hrI = wSubN0ToRI * hrI;

                    dataR[destEvenStartIndex_r] = grR + wSubN0ToRR_hrR - wSubN0ToRI_hrI;
                    dataR[destOddStartIndex_r] = grR - (wSubN0ToRR_hrR - wSubN0ToRI_hrI);
                    dataI[destEvenStartIndex_r] = grI + wSubN0ToRR_hrI + wSubN0ToRI_hrR;
                    dataI[destOddStartIndex_r] = grI - (wSubN0ToRR_hrI + wSubN0ToRI_hrR);

                    // WsubN0ToR *= WsubN0R
                    nextWsubN0ToRR = wSubN0ToRR * wSubN0R - wSubN0ToRI * wSubN0I;
                    nextWsubN0ToRI = wSubN0ToRR * wSubN0I + wSubN0ToRI * wSubN0R;
                    wSubN0ToRR = nextWsubN0ToRR;
                    wSubN0ToRI = nextWsubN0ToRI;
                }
            }

            lastN0 = n0;
            lastLogN0 = logN0;
        }
    }

    private static void postProcess(@NonNull ComplexArray array, boolean normalize) {
        float[] dataR = array.re();
        float[] dataI = array.im();
        int n = array.length();

        if (normalize) {
            float scaleFactor = 1.0f / n;
            for (int i = 0; i < n; ++i) {
                dataR[i] *= scaleFactor;
                dataI[i] *= scaleFactor;
            }
        }

        float re, im;
        for (int i = 0; i < n; ++i) {
            re = dataR[i];
            im = dataI[i];

            if (re < 0.0f) re *= -1f;
            if (im < 0.0f) im *= -1f;

            if (re < ComplexArray.TOL) dataR[i] = 0.0f;
            if (im < ComplexArray.TOL) dataI[i] = 0.0f;
        }
    }

    /**
     * Performs identical index bit reversal shuffles on two arrays of identical
     * size. Each element in the array is swapped with another element based on
     * the bit-reversal of the index. For example, in an array with length 16,
     * item at binary index 0011 (decimal 3) would be swapped with the item at
     * binary index 1100 (decimal 12).
     */
    private static void bitReversalShuffle(@NonNull ComplexArray data) {
        final int n = data.length();
        final int halfOfN = n >> 1;

        float[] a = data.re();
        float[] b = data.im();

        float temp;
        int j = 0;
        for (int i = 0; i < n; i++) {
            if (i < j) {
                // swap indices i & j
                temp = a[i];
                a[i] = a[j];
                a[j] = temp;

                temp = b[i];
                b[i] = b[j];
                b[j] = temp;
            }

            int k = halfOfN;
            while (k <= j && k > 0) {
                j -= k;
                k >>= 1;
            }
            j += k;
        }
    }

    private static boolean isPowerOfTwo(int n) {
        return (n > 0) && ((n & (n - 1)) == 0);
    }

    /**
     * {@code W_SUB_N_R[i]} is the real part of {@code exp(- 2 * i * pi / n)}:
     * {@code W_SUB_N_R[i] = cos(2 * pi/ n)}, where {@code n = 2^i}.
     */
    //@formatter:off
    private static final float[] W_SUB_N_R =
        {  0x1.0p0f, -0x1.0p0f, 0x1.1a62633145c07p-54f, 0x1.6a09e667f3bcdp-1f
        , 0x1.d906bcf328d46p-1f, 0x1.f6297cff75cbp-1f, 0x1.fd88da3d12526p-1f, 0x1.ff621e3796d7ep-1f
        , 0x1.ffd886084cd0dp-1f, 0x1.fff62169b92dbp-1f, 0x1.fffd8858e8a92p-1f, 0x1.ffff621621d02p-1f
        , 0x1.ffffd88586ee6p-1f, 0x1.fffff62161a34p-1f, 0x1.fffffd8858675p-1f, 0x1.ffffff621619cp-1f
        , 0x1.ffffffd885867p-1f, 0x1.fffffff62161ap-1f, 0x1.fffffffd88586p-1f, 0x1.ffffffff62162p-1f
        , 0x1.ffffffffd8858p-1f, 0x1.fffffffff6216p-1f, 0x1.fffffffffd886p-1f, 0x1.ffffffffff621p-1f
        , 0x1.ffffffffffd88p-1f, 0x1.fffffffffff62p-1f, 0x1.fffffffffffd9p-1f, 0x1.ffffffffffff6p-1f
        , 0x1.ffffffffffffep-1f, 0x1.fffffffffffffp-1f, 0x1.0p0f, 0x1.0p0f
        , 0x1.0p0f, 0x1.0p0f, 0x1.0p0f, 0x1.0p0f
        , 0x1.0p0f, 0x1.0p0f, 0x1.0p0f, 0x1.0p0f
        , 0x1.0p0f, 0x1.0p0f, 0x1.0p0f, 0x1.0p0f
        , 0x1.0p0f, 0x1.0p0f, 0x1.0p0f, 0x1.0p0f
        , 0x1.0p0f, 0x1.0p0f, 0x1.0p0f, 0x1.0p0f
        , 0x1.0p0f, 0x1.0p0f, 0x1.0p0f, 0x1.0p0f
        , 0x1.0p0f, 0x1.0p0f, 0x1.0p0f, 0x1.0p0f
        , 0x1.0p0f, 0x1.0p0f, 0x1.0p0f };
    //@formatter:on

    /**
     * {@code W_SUB_N_I[i]} is the imaginary part of
     * {@code exp(- 2 * i * pi / n)}: {@code W_SUB_N_I[i] = -sin(2 * pi/ n)},
     * where {@code n = 2^i}.
     */
    //@formatter:off
    private static final float[] W_SUB_N_I =
        {  0x1.1a62633145c07p-52f, -0x1.1a62633145c07p-53f, -0x1.0p0f, -0x1.6a09e667f3bccp-1f
        , -0x1.87de2a6aea963p-2f, -0x1.8f8b83c69a60ap-3f, -0x1.917a6bc29b42cp-4f, -0x1.91f65f10dd814p-5f
        , -0x1.92155f7a3667ep-6f, -0x1.921d1fcdec784p-7f, -0x1.921f0fe670071p-8f, -0x1.921f8becca4bap-9f
        , -0x1.921faaee6472dp-10f, -0x1.921fb2aecb36p-11f, -0x1.921fb49ee4ea6p-12f, -0x1.921fb51aeb57bp-13f
        , -0x1.921fb539ecf31p-14f, -0x1.921fb541ad59ep-15f, -0x1.921fb5439d73ap-16f, -0x1.921fb544197ap-17f
        , -0x1.921fb544387bap-18f, -0x1.921fb544403c1p-19f, -0x1.921fb544422c2p-20f, -0x1.921fb54442a83p-21f
        , -0x1.921fb54442c73p-22f, -0x1.921fb54442cefp-23f, -0x1.921fb54442d0ep-24f, -0x1.921fb54442d15p-25f
        , -0x1.921fb54442d17p-26f, -0x1.921fb54442d18p-27f, -0x1.921fb54442d18p-28f, -0x1.921fb54442d18p-29f
        , -0x1.921fb54442d18p-30f, -0x1.921fb54442d18p-31f, -0x1.921fb54442d18p-32f, -0x1.921fb54442d18p-33f
        , -0x1.921fb54442d18p-34f, -0x1.921fb54442d18p-35f, -0x1.921fb54442d18p-36f, -0x1.921fb54442d18p-37f
        , -0x1.921fb54442d18p-38f, -0x1.921fb54442d18p-39f, -0x1.921fb54442d18p-40f, -0x1.921fb54442d18p-41f
        , -0x1.921fb54442d18p-42f, -0x1.921fb54442d18p-43f, -0x1.921fb54442d18p-44f, -0x1.921fb54442d18p-45f
        , -0x1.921fb54442d18p-46f, -0x1.921fb54442d18p-47f, -0x1.921fb54442d18p-48f, -0x1.921fb54442d18p-49f
        , -0x1.921fb54442d18p-50f, -0x1.921fb54442d18p-51f, -0x1.921fb54442d18p-52f, -0x1.921fb54442d18p-53f
        , -0x1.921fb54442d18p-54f, -0x1.921fb54442d18p-55f, -0x1.921fb54442d18p-56f, -0x1.921fb54442d18p-57f
        , -0x1.921fb54442d18p-58f, -0x1.921fb54442d18p-59f, -0x1.921fb54442d18p-60f };
    //@formatter:on
}
