package com.oscill;

import androidx.test.ext.junit.runners.AndroidJUnit4;

import com.oscill.types.Dimension;
import com.oscill.types.Unit;
import com.oscill.utils.Log;

import org.junit.Test;
import org.junit.runner.RunWith;

import math.fft.ComplexArray;
import math.fft.Fourier;

@RunWith(AndroidJUnit4.class)
public class MathTest {

    private static final String TAG = "MathTest";

    @Test
    public void testNumFormat() {
        Unit volt = new Unit(Dimension.MILLI, Unit.VOLT);
        Log.i(TAG, volt.format(200f, 0));
        Log.i(TAG, volt.format(400f, 0));
        Log.i(TAG, volt.format(600f, 1));
        Log.i(TAG, volt.format(800f, 0));
        Log.i(TAG, volt.format(1000f, 0));
        Log.i(TAG, volt.format(1200f, 1));
    }

    private static float[] test_data_1() {
        int size = 64;
        float[] data = new float[size];

        float dt = 1f / size;

        for (int i = 0; i < size; i++) {
            float x = dt * i;
            double y = 3 * Math.sin(x * 50f) + Math.sin(x * 70f) + Math.sin(x * 60f);
            data[i] = (float) y;
        }

        return data;
    }

    @Test
    public void testFourier() {
        ComplexArray data = new ComplexArray(test_data_1());
        Log.i(TAG, "Data: ", data);

        Fourier fourier = new Fourier();
        ComplexArray forward = fourier.forwardDFT(data);
        Log.i(TAG, "Forward: ", forward);

        ComplexArray nativeFFT = data.naiveForwardDFT();
        Log.i(TAG, "Native: ", nativeFFT);

//        ComplexArray inverse = fourier.inverseDFT(forward);
//        Log.i(TAG, "Inverse: ", inverse);

        ComplexArray diff = ComplexArray.elementWiseProduct(data, nativeFFT);
        Log.i(TAG, "Diff: ", diff);
    }
}
