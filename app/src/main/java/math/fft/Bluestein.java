package math.fft;

import androidx.annotation.NonNull;

/**
 * Bluestein chirp-z transform
 */
class Bluestein {

    private int N = 0;

    private float[] sin;
    private float[] cos;

    Bluestein() {
    }

    private void calcSinCos(int n) {
        float[] sin = new float[n];
        float[] cos = new float[n];
        for (int i = 0; i < n; ++i) {
            int j = (int) ((long) i * i % (n * 2));
            float angle = (float)Math.PI * j / n;
            cos[i] = (float) Math.cos(angle);
            sin[i] = (float) Math.sin(angle);
        }
        this.sin = sin;
        this.cos = cos;
    }

    @NonNull
    ComplexArray forwardDFT(@NonNull ComplexArray array) {
        int n = array.length();
        checkN(n);

        float[] data = array.re();
        float[] imag = array.im();

        // find a power of 2 convolution length m such that m >= n * 2 + 1
        int m = Integer.highestOneBit(n) * 4;

        // temporary arrays
        ComplexArray a = new ComplexArray(m);
        float[] a_re = a.re();
        float[] a_im = a.im();

        ComplexArray b = new ComplexArray(m);
        float[] b_re = b.re();
        float[] b_im = b.im();

        b_re[0] = cos[0];
        b_im[0] = sin[0];

        float sin_i, cos_i, c_re_i, c_im_i, re_i, im_i, abs_re_i, abs_im_i;

        for (int i = 0; i < n; ++i) {
            sin_i = sin[i];
            cos_i = cos[i];
            re_i = data[i];
            im_i = imag[i];
            a_re[i] = re_i * cos_i + im_i * sin_i;
            a_im[i] = -re_i * sin_i + im_i * cos_i;
            if (i != 0) {
                b_re[i] = b_re[m - i] = cos_i;
                b_im[i] = b_im[m - i] = sin_i;
            }
        }

        // convolution
        ComplexArray conv = convolve(a, b);
        float[] c_re = conv.re();
        float[] c_im = conv.im();

        // result
        ComplexArray res = new ComplexArray(n);
        float[] re = res.re();
        float[] im = res.im();

        // postprocessing
        for (int i = 0; i < n; ++i) {
            sin_i = sin[i];
            cos_i = cos[i];
            c_re_i = c_re[i];
            c_im_i = c_im[i];

            re_i = c_re_i * cos_i + c_im_i * sin_i;
            im_i = -c_re_i * sin_i + c_im_i * cos_i;

            abs_re_i = re_i < 0.0f ? -re_i : re_i;
            abs_im_i = im_i < 0.0f ? -im_i : im_i;

            re[i] = (abs_re_i <= ComplexArray.TOL) ? 0.0f : re_i;
            im[i] = (abs_im_i <= ComplexArray.TOL) ? 0.0f : im_i;
        }

        return res;
    }

    @NonNull
    ComplexArray inverseDFT(@NonNull ComplexArray freqs) {
        ComplexArray inv = forwardDFT(freqs);
        float[] re = inv.re();
        float[] im = inv.im();
        final int n = re.length;
        for (int i = 0; i < n; ++i) {
            float re_i = re[i] / n;
            float im_i = im[i] / n;
            re[i] = (Math.abs(re_i) <= ComplexArray.TOL) ? 0.0f : re_i;
            im[i] = (Math.abs(im_i) <= ComplexArray.TOL) ? 0.0f : im_i;
        }
        for (int i = 1; i <= n / 2; ++i) {
            float re_tmp = re[n - i];
            float im_tmp = im[n - i];
            re[n - i] = re[i];
            re[i] = re_tmp;
            im[n - i] = im[i];
            im[i] = im_tmp;
        }
        return inv;
    }

    @NonNull
    private static ComplexArray convolve(@NonNull ComplexArray x, @NonNull ComplexArray y) {
        x = Fourier.forwardDFT_pow2(x);
        y = Fourier.forwardDFT_pow2(y);

        float[] x_re = x.re();
        float[] x_im = x.im();
        float[] y_re = y.re();
        float[] y_im = y.im();

        for (int i = 0; i < x_re.length; ++i) {
            float x_re_i = x_re[i];
            float y_re_i = y_re[i];
            float x_im_i = x_im[i];
            float y_im_i = y_im[i];
            x_re[i] = x_re_i * y_re_i - x_im_i * y_im_i;
            x_im[i] = x_im_i * y_re_i + x_re_i * y_im_i;
        }

        return Fourier.inverseDFT_pow2(new ComplexArray(x_re, x_im));
    }

    private void checkN(int N) {
        if (this.N != N) {
            this.N = N;
            calcSinCos(N);
        }
    }

}
