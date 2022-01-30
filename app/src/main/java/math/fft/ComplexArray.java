package math.fft;

import androidx.annotation.NonNull;

/**
 * For computations with arrays of complex numbers.
 */
public final class ComplexArray {

    /** The IEEE 754 machine epsilon from Cephes: {@code (2^-53)} */
    private static final float MACH_EPS = 1.11022302462515654042e-16f;
    static final float TOL = 5.0f * MACH_EPS;
    private static final float TWO_PI = 2.0f * (float)Math.PI;

    private final int size;
    private final float[] re;
    private final float[] im;

    private ComplexArray mag_phase;

    public ComplexArray(int size) {
        this.size = size;
        this.re = new float[size];
        this.im = new float[size];
    }

    public ComplexArray(@NonNull float[] re) {
        this(re, new float[re.length]);
    }

    public ComplexArray(@NonNull float[] re, @NonNull float[] im) {
        if (re.length != im.length) {
            throw new IllegalArgumentException(re.length + " != " + im.length);
        }
        this.size = re.length;
        this.re = re;
        this.im = im;
    }

    @NonNull
    public ComplexArray copy() {
        return new ComplexArray(re.clone(), im.clone());
    }

    private static final double E1 = 1.0 / Math.E;

    @NonNull
    public ComplexArray getMagnitudePhase() {
        if (mag_phase == null) {
            int resSize = size / 2;
            ComplexArray res = new ComplexArray(resSize);
            float[] mag = res.re();
            float[] phase = res.im();

            float _re, _im;
            for (int idx = 0; idx < resSize; idx++) {
                _re = re[idx];
                _im = im[idx];
                mag[idx] = (float) Math.pow(_re * _re + _im * _im, E1);
                phase[idx] = (float) Math.atan2(_im, _re);
            }
            mag_phase = res;
        }

        return mag_phase;
    }

    @NonNull
    public ComplexArray naiveForwardDFT() {
        return naiveDFT(-1.0f, this, 1.0f);
    }

    @NonNull
    public ComplexArray naiveInverseDFT() {
        return naiveDFT(1.0f, this, (1.0f / size));
    }

    @NonNull
    private static ComplexArray naiveDFT(float sign, @NonNull ComplexArray array, float scale) {
        float[] re = array.re();
        float[] im = array.im();
        int N = array.size;

        float[] imag = new float[N];
        float[] real = new float[N];
        float[] cos = new float[N];
        float[] sin = new float[N];

        for (int i = 0; i < N; ++i) {
            float angle = (sign * TWO_PI * i) / N;
            cos[i] = (float) Math.cos(angle);
            sin[i] = (float) Math.sin(angle);
        }

        for (int i = 0; i < N; ++i) {
            float rZ = 0.0f;
            float iZ = 0.0f;
            for (long j = 0; j < N; ++j) {
                int idx = (int) ((i * j) % N);
                float cos_i = cos[idx];
                float sin_i = sin[idx];
                float rX = re[(int) j];
                float iY = (im == null) ? 0.0f : im[(int) j];
                rZ += cos_i * rX - sin_i * iY;
                iZ += sin_i * rX + cos_i * iY;
            }
            float x = scale * rZ;
            float y = scale * iZ;
            if (Math.abs(x) <= TOL) {
                x = 0.0f;
            }
            if (Math.abs(y) <= TOL) {
                y = 0.0f;
            }
            real[i] = x;
            imag[i] = y;
        }
        return new ComplexArray(real, imag);
    }

    public float[] absSquared() {
        return absSquaredScaled(false);
    }

    // for power density spectrum
    public float[] absSquaredScaled() {
        return absSquaredScaled(true);
    }

    private float[] absSquaredScaled(boolean withScaling) {
        float[] real = re;
        float[] imag = im;
        int N = real.length;
        float[] res = new float[N];
        float scale = withScaling ? N : 1.0f;
        for (int i = 0; i < N; ++i) {
            float rX = real[i];
            float iY = imag[i];
            float square = (rX * rX + iY * iY) / scale;
            if (square <= TOL) {
                square = 0.0f;
            }
            res[i] = square;
        }
        return res;
    }

    public ComplexArray fftshift() {
        return shift(false);
    }

    public ComplexArray ifftshift() {
        return shift(true);
    }

    private ComplexArray shift(boolean inverse) {
        final int length = re.length;
        int mid = -1;
        float[] re_this = re;
        float[] im_this = im;
        float[] re_shift = new float[length];
        float[] im_shift = new float[length];
        if (length % 2 == 0) {
            mid = (length / 2);
            System.arraycopy(re_this, 0, re_shift, mid, mid);
            System.arraycopy(re_this, mid, re_shift, 0, mid);
            System.arraycopy(im_this, 0, im_shift, mid, mid);
            System.arraycopy(im_this, mid, im_shift, 0, mid);
        } else {
            mid = (length - 1) / 2;
            if (inverse) {
                System.arraycopy(re_this, 0, re_shift, mid + 1, mid);
                System.arraycopy(re_this, mid, re_shift, 0, mid + 1);
                System.arraycopy(im_this, 0, im_shift, mid + 1, mid);
                System.arraycopy(im_this, mid, im_shift, 0, mid + 1);
            } else {
                System.arraycopy(re_this, 0, re_shift, mid, mid + 1);
                System.arraycopy(re_this, mid + 1, re_shift, 0, mid);
                System.arraycopy(im_this, 0, im_shift, mid, mid + 1);
                System.arraycopy(im_this, mid + 1, im_shift, 0, mid);
            }
        }
        return new ComplexArray(re_shift, im_shift);
    }

    public static float[] dot(ComplexArray a, ComplexArray b) {
        if (a.length() != b.length()) {
            throw new IllegalArgumentException("Unequal dimensions: " + a.length() + " != " + b.length());
        }
        if (a.length() == 0) {
            throw new IllegalArgumentException("Arrays are empty: length = 0");
        }
        float res_re = 0.0f;
        float res_im = 0.0f;
        float[] a_re_ = a.re;
        float[] b_re_ = b.re;
        float[] a_im_ = a.im;
        float[] b_im_ = b.im;
        for (int i = 0; i < a_re_.length; ++i) {
            float a_re = a_re_[i];
            float b_re = b_re_[i];
            float a_im = a_im_[i];
            float b_im = b_im_[i];
            float re_i = a_re * b_re - a_im * b_im;
            float im_i = a_re * b_im + a_im * b_re;
            re_i = (Math.abs(re_i) <= TOL) ? 0.0f : re_i;
            im_i = (Math.abs(im_i) <= TOL) ? 0.0f : im_i;
            res_re += re_i;
            res_im += im_i;
        }
        res_re = (Math.abs(res_re) <= TOL) ? 0.0f : res_re;
        res_im = (Math.abs(res_im) <= TOL) ? 0.0f : res_im;
        return new float[] { res_re, res_im };
    }

    @NonNull
    public static ComplexArray elementWiseProduct(@NonNull ComplexArray a, @NonNull ComplexArray b) {
        if (a.length() != b.length()) {
            throw new IllegalArgumentException("Unequal dimensions: " + a.length() + " != " + b.length());
        }
        float[] real = new float[a.length()];
        float[] imag = new float[a.length()];
        float[] a_re_ = a.re;
        float[] b_re_ = b.re;
        float[] a_im_ = a.im;
        float[] b_im_ = b.im;
        for (int i = 0; i < a_re_.length; ++i) {
            float a_re = a_re_[i];
            float b_re = b_re_[i];
            float a_im = a_im_[i];
            float b_im = b_im_[i];
            float re_i = a_re * b_re - a_im * b_im;
            float im_i = a_re * b_im + a_im * b_re;
            re_i = (Math.abs(re_i) <= TOL) ? 0.0f : re_i;
            im_i = (Math.abs(im_i) <= TOL) ? 0.0f : im_i;
            real[i] = re_i;
            imag[i] = im_i;
        }
        return new ComplexArray(real, imag);
    }

    @NonNull
    public float[] re() {
        return re;
    }

    @NonNull
    public float[] im() {
        return im;
    }

    public int length() {
        return size;
    }

    @Override
    @NonNull
    public String toString() {
        int max = length() - 1;
        if (max == -1) {
            return "[]";
        }
        StringBuilder b = new StringBuilder(40 * (max + 1));
        b.append("\n");
        b.append('[');
        for (int i = 0; i < max; i++) {
            b.append("\n");
            b.append(i).append(": ").append(re[i]).append("  ").append(im[i]).append('i');
        }
        b.append("\n");
        return b.append(']').toString();
    }

}
