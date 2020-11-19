package com.oscill.utils;

import android.annotation.SuppressLint;
import android.app.ActivityManager;
import android.app.Application;
import android.content.ContentResolver;
import android.content.Context;
import android.content.pm.ApplicationInfo;
import android.content.pm.PackageInfo;
import android.content.pm.PackageManager;

import androidx.annotation.NonNull;
import androidx.annotation.Nullable;
import androidx.core.content.ContextCompat;

import java.lang.reflect.Field;
import java.lang.reflect.Method;
import java.util.HashMap;
import java.util.List;
import java.util.Map;

public class AppContextWrapper {

    private static final String TAG = Log.getTag(AppContextWrapper.class);

    private static final SuspendValue<Context> mAppContext = new SuspendValue<>(AppContextWrapper::getApplicationUsingReflection);

    @NonNull
    @SuppressLint("PrivateApi")
    @SuppressWarnings("JavaReflectionInvocation")
    private static Application getApplicationUsingReflection() {
        try {
            return (Application) Class.forName("android.app.ActivityThread")
                    .getMethod("currentApplication")
                    .invoke(null, (Object[]) null);
        } catch (Exception ignored) {
        }
        throw new IllegalStateException();
    }

    @Nullable
    private static String getProcessNameUsingReflection() {
        String processName = null;
        try {
            Application app = (Application)getAppContext();
            Field loadedApkField = app.getClass().getField("mLoadedApk");
            loadedApkField.setAccessible(true);
            Object loadedApk = loadedApkField.get(app);

            Field activityThreadField = loadedApk.getClass().getDeclaredField("mActivityThread");
            activityThreadField.setAccessible(true);
            Object activityThread = activityThreadField.get(loadedApk);

            Method getProcessName = activityThread.getClass().getDeclaredMethod("getProcessName");
            processName = (String) getProcessName.invoke(activityThread);
        } catch (Exception e) {
            Log.e(TAG, e);
        }
        return processName;
    }

    @Nullable
    private static String getProcessNameFromActivityManager() {
        ActivityManager manager = getSystemService(Context.ACTIVITY_SERVICE);
        List<ActivityManager.RunningAppProcessInfo> infos = manager.getRunningAppProcesses();
        if (infos != null) {
            int pid = android.os.Process.myPid();
            for (ActivityManager.RunningAppProcessInfo processInfo : infos) {
                if (processInfo.pid == pid) {
                    return processInfo.processName;
                }
            }
        }
        return null;
    }

    @NonNull
    public static Context getAppContext() {
        return mAppContext.get();
    }

    public static void setAppContext(@NonNull Context appContext) {
        mAppContext.set(appContext);
    }

    @NonNull
    public static ContentResolver getContentResolver() {
        return getAppContext().getContentResolver();
    }

    @NonNull
    public static String getPackageName() {
        return getAppContext().getPackageName();
    }

    @NonNull
    public static PackageManager getPackageManager() {
        return getAppContext().getPackageManager();
    }

    private static SuspendValue<String> processName = new SuspendValue<>(() -> {
        String res = getProcessNameUsingReflection();
        if (res == null) {
            res = getProcessNameFromActivityManager();
        }
        return res;
    });

    @Nullable
    public static String getProcessName() {
        return processName.get();
    }

    public static boolean isBaseProcess() {
        return StringUtils.equals(getPackageName(), getProcessName());
    }

    @NonNull
    public static ApplicationInfo getApplicationInfo() {
        return getAppContext().getApplicationInfo();
    }

    @NonNull
    public static PackageInfo getPackageInfo() {
        try {
            return getPackageManager().getPackageInfo(getPackageName(), 0);
        } catch (PackageManager.NameNotFoundException ignored) {
        }

        throw new IllegalStateException();
    }

    @NonNull
    private static <T> T getSystemService(@NonNull String serviceName) {
        return ObjectUtils.castOrThrow(getAppContext().getSystemService(serviceName));
    }

    private static final SuspendValue<Map<Class<?>, String>> systemServicesMap = new SuspendValue<>(() -> {
        Map<Class<?>, String> map = new HashMap<>(32);
        map.put(android.view.WindowManager.class, Context.WINDOW_SERVICE);
        map.put(android.net.ConnectivityManager.class, Context.CONNECTIVITY_SERVICE);
        map.put(android.app.ActivityManager.class, Context.ACTIVITY_SERVICE);
        map.put(android.view.inputmethod.InputMethodManager.class, Context.INPUT_METHOD_SERVICE);
        map.put(android.view.LayoutInflater.class, Context.LAYOUT_INFLATER_SERVICE);
        map.put(android.app.AlarmManager.class, Context.ALARM_SERVICE);
        map.put(android.app.NotificationManager.class, Context.NOTIFICATION_SERVICE);
        map.put(android.location.LocationManager.class, Context.LOCATION_SERVICE);
        map.put(android.media.AudioManager.class, Context.AUDIO_SERVICE);
        map.put(android.net.wifi.WifiManager.class, Context.WIFI_SERVICE);
        map.put(android.telephony.TelephonyManager.class, Context.TELEPHONY_SERVICE);
        map.put(android.os.PowerManager.class, Context.POWER_SERVICE);
        map.put(android.app.UiModeManager.class, Context.UI_MODE_SERVICE);
        map.put(android.os.storage.StorageManager.class, Context.STORAGE_SERVICE);
        map.put(android.hardware.SensorManager.class, Context.SENSOR_SERVICE);
        map.put(android.app.KeyguardManager.class, Context.KEYGUARD_SERVICE);
        map.put(android.app.SearchManager.class, Context.SEARCH_SERVICE);
        map.put(android.content.ClipboardManager.class, Context.CLIPBOARD_SERVICE);
        map.put(android.hardware.usb.UsbManager.class, Context.USB_SERVICE);

        return map;
    });

    @NonNull
    public static <T> T getSystemService(@NonNull Class<T> serviceClass) {
        String serviceName = systemServicesMap.get().get(serviceClass);
        return getSystemService(serviceName);
    }

    public static boolean checkPermission(@NonNull String permission) {
        try {
            return ContextCompat.checkSelfPermission(getAppContext(), permission) == PackageManager.PERMISSION_GRANTED;
        } catch (RuntimeException e) {
            Log.e(TAG, e);
        }

        return false;
    }

    public static boolean checkPermissions(@NonNull String... permissions) {
        for (String permission : permissions) {
            if (!checkPermission(permission)) {
                return false;
            }
        }
        return true;
    }

}
