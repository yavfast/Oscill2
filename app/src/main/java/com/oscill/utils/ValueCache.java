package com.oscill.utils;

import android.os.SystemClock;

import androidx.annotation.NonNull;
import androidx.annotation.Nullable;
import androidx.collection.LruCache;

import com.oscill.utils.executor.ObjCallable;

import java.util.Map;
import java.util.concurrent.ConcurrentHashMap;

public class ValueCache<K,V> {

    private final ObjCallable<K,V> valueCreator;
    private final Map<K,Long> cachedKeys = new ConcurrentHashMap<>();
    private final ValuesLruCache cache;
    private long expired = 0L;

    public ValueCache(@NonNull ObjCallable<K,V> valueCreator) {
        this(Integer.MAX_VALUE, valueCreator);
    }

    public ValueCache(int maxSize, @NonNull ObjCallable<K,V> valueCreator) {
        this.valueCreator = valueCreator;
        this.cache = new ValuesLruCache(maxSize);
    }

    public void setExpired(long expired) {
        this.expired = expired;
    }

    private void addKeyInfo(@NonNull K key) {
        cachedKeys.put(key, SystemClock.elapsedRealtime());
    }

    public synchronized void add(@NonNull K key, @NonNull V value) {
        cache.put(key, value);
        addKeyInfo(key);
    }

    private void checkExpired(@NonNull K key) {
        if (expired > 0L) {
            long now = SystemClock.elapsedRealtime();
            Long created = cachedKeys.get(key);
            if (created != null && (now - created > expired)) {
                cache.remove(key);
            }
        }
    }

    public synchronized V get(@NonNull K key) {
        checkExpired(key);
        return cache.get(key);
    }

    public boolean contains(@Nullable K key) {
        return key != null && cachedKeys.containsKey(key);
    }

    public synchronized void evictAll() {
        cache.evictAll();
    }

    public synchronized void remove(@NonNull K key) {
        cache.remove(key);
    }

    private class ValuesLruCache extends LruCache<K,V> {

        public ValuesLruCache(int maxSize) {
            super(maxSize);
        }

        @Override
        protected V create(@NonNull K key) {
            V res = valueCreator.call(key);
            if (res != null) {
                addKeyInfo(key);
            }
            return res;
        }

        @Override
        protected void entryRemoved(boolean evicted, K key, V oldValue, V newValue) {
            if (newValue == null) {
                cachedKeys.remove(key);
            }
        }

    }

}
