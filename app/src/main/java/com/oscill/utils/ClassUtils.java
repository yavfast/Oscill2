package com.oscill.utils;

import androidx.annotation.NonNull;
import androidx.annotation.Nullable;

import java.lang.reflect.Constructor;
import java.lang.reflect.Field;
import java.lang.reflect.Method;
import java.util.Collection;
import java.util.Map;
import java.util.concurrent.ConcurrentHashMap;

public class ClassUtils {

    private static final String TAG = Log.getTag(ClassUtils.class, Log.Level.WARN);

    @SuppressWarnings("unchecked")
    @NonNull
    public static <T> T cast(@NonNull Object object) {
        return (T) object;
    }

    @SuppressWarnings("unchecked")
    @Nullable
    public static <T> T castOrNull(@Nullable Object object) {
        return object != null ? (T) object : null;
    }

    @Nullable
    public static <T> Class<T> getClassByName(@NonNull String className) {
        try {
            Class<?> res = Class.forName(className);
            return ObjectUtils.cast(res);
        } catch (ClassNotFoundException e) {
            Log.e(TAG, e);
        }
        return null;
    }

    @Nullable
    private static Class<?>[] getParameterTypes(@Nullable Object... args) {
        Class<?>[] parameterTypes = null;
        if (!ArrayUtils.isEmpty(args)) {
            parameterTypes = new Class<?>[args.length];
            for (int idx = 0; idx < args.length; idx++) {
                parameterTypes[idx] = args[idx].getClass();
            }
        }
        return parameterTypes;
    }

    @NonNull
    private static <T> Constructor<T> getConstructor(@NonNull Class<T> clazz, @Nullable Class<?>... params) throws NoSuchMethodException {
        if (params != null && params.length > 0) {
            Constructor<?>[] constructors = clazz.getDeclaredConstructors();
            for (Constructor<?> constructor : constructors) {
                Class<?>[] paramTypes = constructor.getParameterTypes();
                if (paramTypes.length == params.length) {
                    boolean found = true;

                    for (int paramIdx = 0; paramIdx < paramTypes.length; paramIdx++) {
                        if (!isInstanceOf(params[paramIdx], paramTypes[paramIdx])) {
                            found = false;
                            break;
                        }
                    }

                    if (found) {
                        return cast(constructor);
                    }
                }
            }

        }

        return clazz.getDeclaredConstructor(params);
    }

    @NonNull
    public static <T> T newInstance(@NonNull Class<T> clazz, @Nullable Object... args) throws Exception {
        Constructor<T> sMethodImpl = getConstructor(clazz, getParameterTypes(args));
        return sMethodImpl.newInstance(args);
    }

    @Nullable
    public static <T> T newInstanceSafe(@NonNull Class<T> clazz, @Nullable Object... args) {
        try {
            Constructor<T> sMethodImpl = getConstructor(clazz, getParameterTypes(args));
            sMethodImpl.newInstance(args);
        } catch (Exception e) {
            Log.e(TAG, e.getMessage(), e);
        }
        return null;
    }

    @Nullable
    public static <T> T getInstance(@NonNull String className, @Nullable Object... args) {
        Class<T> clazz = getClassByName(className);
        if (clazz != null) {
            try {
                return getInstance(clazz, args);
            } catch (Exception e) {
                Log.e(TAG, e);
            }
        }
        return null;
    }

    @NonNull
    public static <T> T getInstance(@NonNull Class<T> clazz, @Nullable Object... args) throws Exception {
        try {
            T res = invokeStatic(clazz, "getInstance", args);
            if (res != null) {
                return res;
            }
        } catch (NoSuchMethodException e) {
            Log.w(TAG, "Method getInstance() not found in class ", clazz.getName());
        }
        return newInstance(clazz, args);
    }

    @Nullable
    public static <T> T invokeStatic(@NonNull Class<?> clazz, @NonNull String methodName, @Nullable Object... args) throws Exception {
        Method sMethodImpl;
        try {
            sMethodImpl = clazz.getMethod(methodName, getParameterTypes(args));
        } catch (NoSuchMethodException e) {
            Log.w(TAG, "Method ", methodName, " not found in class ", clazz.getName());
            throw e;
        }
        return castOrNull(sMethodImpl.invoke(clazz, args));
    }

    @Nullable
    public static <T> T invoke(@NonNull Object obj, @NonNull String methodName, @Nullable Object... args) throws Exception {
        Method sMethodImpl;
        try {
            sMethodImpl = obj.getClass().getMethod(methodName, getParameterTypes(args));
        } catch (NoSuchMethodException e) {
            Log.w(TAG, "Method ", methodName, " not found in class ", obj.getClass().getName());
            throw e;
        }
        return castOrNull(sMethodImpl.invoke(obj, args));
    }

    private static final Map<Class<?>,Object> sSingletonsInstances = new ConcurrentHashMap<>(64);

    @Nullable
    public static <T> T getSingleton(@NonNull String className, @Nullable Object... args) {
        Class<T> clazz = getClassByName(className);
        if (clazz != null) {
            return getSingleton(clazz, args);
        }
        return null;
    }

    @NonNull
    public static <T> T getSingleton(@NonNull Class<T> clazz, @Nullable Object... args) {
        T singleton = castOrNull(sSingletonsInstances.get(clazz));
        if (singleton == null) {
            synchronized (clazz) {
                singleton = castOrNull(sSingletonsInstances.get(clazz));
                if (singleton == null) {
                    try {
                        singleton = getInstance(clazz, args);
                        sSingletonsInstances.put(clazz, singleton);
                    } catch (Exception e) {
                        Log.e(TAG, e);
                        throw new IllegalArgumentException(e);
                    }
                }
            }
        }
        return singleton;
    }

    @Nullable
    public static Field getClassField(@NonNull String className, @NonNull String fieldName) {
        Class<?> clazz = getClassByName(className);
        if (clazz != null) {
            return getClassField(clazz, fieldName);
        }
        return null;
    }

    @Nullable
    public static Field getClassField(@NonNull Class<?> clazz, @NonNull String fieldName) {
        try {
            Field field = clazz.getDeclaredField(fieldName);
            if (field != null) {
                setFieldAccessible(field);
            }
            return field;
        } catch (Throwable e) {
            Log.w(TAG, e);
        }
        return null;
    }

    @Nullable
    public static <T> T getFieldValue(@NonNull Object object, @NonNull Field field) {
        try {
            return cast(field.get(object));
        } catch (Throwable e) {
            Log.w(TAG, e);
        }
        return null;
    }

    @Nullable
    public static <T> T getFieldValue(@NonNull Object object, @NonNull String fieldName) {
        Field field = getClassField(object.getClass(), fieldName);
        if (field != null) {
            return getFieldValue(object, field);
        }
        return null;
    }

    @Nullable
    public static <T> T getStaticFieldValue(@NonNull String className, @NonNull String fieldName) {
        Field field = getClassField(className, fieldName);
        if (field != null) {
            try {
                return cast(field.get(null));
            } catch (Throwable e) {
                Log.e(TAG, e);
            }
        }
        return null;
    }

    public static boolean setStaticFieldValue(@NonNull String className, @NonNull String fieldName, Object value) {
        Field field = getClassField(className, fieldName);
        if (field != null) {
            return setFieldValue(null, field, value);
        }
        return false;
    }

    public static boolean setFieldValue(@NonNull Object object, @NonNull String fieldName, Object value) {
        Field field = getClassField(object.getClass(), fieldName);
        if (field != null) {
            return setFieldValue(object, field, value);
        }
        return false;
    }

    public static boolean setFieldValue(@Nullable Object object, @NonNull Field field, Object value) {
        try {
            setFieldAccessible(field);
            field.set(object, value);
            return true;
        } catch (Throwable e) {
            Log.e(TAG, e);
        }
        return false;
    }

    public static void setFieldAccessible(@NonNull Field field) {
        if (!field.isAccessible()) {
            field.setAccessible(true);
        }
    }

    public static boolean isAssignableFrom(@Nullable Class<?> clazz, @NonNull Class<?>... fromClasses) {
        if (clazz != null) {
            for (Class<?> fromClass : fromClasses) {
                if (clazz.isAssignableFrom(fromClass)) {
                    return true;
                }
            }
        }
        return false;
    }

    public static boolean isAssignableFrom(@Nullable String className, @NonNull Class<?>... fromClasses) {
        return isAssignableFrom(getClassByName(className), fromClasses);
    }

    public static boolean isInstanceOf(@Nullable String className, @NonNull Class<?>... instanceOfClasses) {
        return isInstanceOf(getClassByName(className), instanceOfClasses);
    }

    public static boolean isInstanceOf(@Nullable Object obj, @NonNull Class<?>... instanceOfClasses) {
        return obj != null && isInstanceOf(obj.getClass(), instanceOfClasses);
    }

    public static boolean isInstanceOf(@Nullable Class<?> clazz, @NonNull Class<?>... instanceOfClasses) {
        if (clazz != null) {
            for (Class<?> instanceOfClass : instanceOfClasses) {
                if (instanceOfClass.isAssignableFrom(clazz)) {
                    return true;
                }
            }
        }
        return false;
    }

    @NonNull
    public static String getClassTag(@NonNull Class<?> clazz) {
        String simpleName = clazz.getName();
        final int dotPos = simpleName.lastIndexOf('.');
        if (dotPos > 0) {
            return simpleName.substring(dotPos + 1); // strip the package name
        }

        return simpleName;
    }

    public static <T> int findItemByClassType(@NonNull Collection<?> collection, @NonNull Class<T> itemClassType) {
        int res = 0;
        for (Object item : collection) {
            if (isInstanceOf(item.getClass(), itemClassType)) {
                return res;
            }
            res++;
        }
        return -1;
    }


}
