package com.oscill;

import androidx.test.ext.junit.runners.AndroidJUnit4;

import com.oscill.types.Dimension;
import com.oscill.types.Unit;
import com.oscill.utils.Log;

import org.junit.Test;
import org.junit.runner.RunWith;

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
}
