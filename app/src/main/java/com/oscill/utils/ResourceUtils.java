package com.oscill.utils;

import android.content.BroadcastReceiver;
import android.content.Context;
import android.content.Intent;
import android.content.IntentFilter;
import android.content.res.Resources;
import android.text.Spanned;
import android.util.TypedValue;

import androidx.annotation.DimenRes;
import androidx.annotation.NonNull;
import androidx.annotation.Nullable;
import androidx.annotation.PluralsRes;
import androidx.annotation.StringRes;

import com.oscill.utils.executor.Executor;

import java.lang.reflect.Field;

public class ResourceUtils {

    private static final String TAG = Log.getTag(ResourceUtils.class);

    @NonNull
    public static Resources getResources() {
        return getResources(AppContextWrapper.getAppContext());
    }

    @NonNull
    public static Resources getResources(@NonNull Context context) {
        return context.getResources();
    }

    private final static ValueCache<Integer, String> sResourceStrings = new ValueCache<>(256, resId ->
            AppContextWrapper.getAppContext().getString(resId)
    );

    private final static ValueCache<String, Integer> sResourceResIdByName = new ValueCache<>(resName ->
            getIdentifier(resName, "string")
    );

    private final static ValueCache<Integer, String> sResourceSysStrings = new ValueCache<>(resId ->
            Resources.getSystem().getString(resId)
    );

    private final static ValueCache<String, Integer> sResourceSysResIdByName = new ValueCache<>(resName ->
            Resources.getSystem().getIdentifier(resName, "string", "android")
    );

    private static final BroadcastReceiver mLocaleChangedReceiver = new BroadcastReceiver() {
        @Override
        public void onReceive(Context context, Intent intent) {
            onLocaleChanged();
        }
    };

    static {
        Executor.runInTaskQueue(() ->
                AppContextWrapper.getAppContext().registerReceiver(mLocaleChangedReceiver, new IntentFilter(Intent.ACTION_LOCALE_CHANGED))
        );
    }

    public static void onLocaleChanged() {
        Executor.runInBackgroundAsync(() -> {
            sResourceStrings.evictAll();
            sResourceSysStrings.evictAll();
        });
    }

    public static boolean isValidResId(int resId) {
        switch (resId) {
            case 0:
            case -1:
                return false;

            default:
                return true;
        }
    }

    public static int getIdentifier(@NonNull String resName, @NonNull String defType) {
        return getResources().getIdentifier(resName, defType, AppContextWrapper.getPackageName());
    }

    @NonNull
    public static String getString(@StringRes int resId) {
        return sResourceStrings.get(resId);
    }

    @Nullable
    public static String tryGetString(@StringRes int resId) {
        return isValidResId(resId) ? sResourceStrings.get(resId) : null;
    }

    @NonNull
    public static String getString(@StringRes int resId, Object... formatArgs) {
        String raw = getString(resId);
        return String.format(raw, formatArgs);
    }

    @NonNull
    public static String getStringOfIds(@StringRes int resId, Integer... formatArgsResIds) {
        String raw = getString(resId);
        String[] arr = ArrayUtils.toArray(ArrayUtils.convert(ArrayUtils.toArrayList(formatArgsResIds), ResourceUtils::getString), String.class);
        return String.format(raw, (Object[]) arr);
    }

    @NonNull
    public static String getString(@NonNull String resName) {
        return getString(sResourceResIdByName.get(resName));
    }

    @NonNull
    public static String getQuantityString(@PluralsRes int resId, int quantity) {
        return getQuantityString(resId, quantity, quantity);
    }

    @NonNull
    public static String getQuantityString(@PluralsRes int resId, int quantity, Object... formatArgs) {
        return getResources().getQuantityString(resId, quantity, formatArgs);
    }

    public static int getRawResId(@NonNull String resName) {
        return getIdentifier(resName, "raw");
    }

    public static int getResId(@NonNull String resName, @NonNull Class<?> resourceClass) {
        try {
            Field idField = resourceClass.getDeclaredField(resName);
            return idField.getInt(idField);
        } catch (Exception e) {
            Log.e(TAG, "Resource not found: ", resName, " in class: ", resourceClass.getName());
            return -1;
        }
    }
    @NonNull
    public static String getSystemString(int resId) {
        return sResourceSysStrings.get(resId);
    }

    public static int getSystemResId(@NonNull String resName, @NonNull String defType) {
        switch (defType) {
            case "string":
                return sResourceSysResIdByName.get(resName);

            default:
                return Resources.getSystem().getIdentifier(resName, defType, "android");

        }
    }

    public static float getDimension(@DimenRes int id) {
        return getResources().getDimension(id);
    }

    public static int getDimensionPixelSize(@DimenRes int id) {
        return getResources().getDimensionPixelSize(id);
    }

    public static int dpToPx(float dp) {
        return (int) TypedValue.applyDimension(TypedValue.COMPLEX_UNIT_DIP, dp, getResources().getDisplayMetrics());
    }

    public static int dpToPx(@DimenRes int resId) {
        return getResources().getDimensionPixelSize(resId);
    }

}
