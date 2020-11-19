package com.oscill.utils;

import android.util.SparseArray;

import androidx.annotation.NonNull;
import androidx.annotation.Nullable;

import java.lang.reflect.Array;
import java.util.ArrayList;
import java.util.Arrays;
import java.util.Collection;
import java.util.Collections;
import java.util.Comparator;
import java.util.HashSet;
import java.util.Iterator;
import java.util.List;
import java.util.Map;
import java.util.Set;

public class ArrayUtils {

    @NonNull
    @SafeVarargs
    @SuppressWarnings("unchecked")
    public static <T> T[] join(@NonNull T[]... arrays) {
        int size = 0;
        for (T[] array : arrays) {
            size += !isEmpty(array) ? array.length : 0;
        }

        if (size > 0) {
            ArrayList<T> result = new ArrayList<>(size);

            for (T[] array : arrays) {
                result.addAll(Arrays.asList(array));
            }

            return toArray(result, (Class<T>) arrays[0].getClass().getComponentType());
        }

        return arrays[0];
    }

    @NonNull
    @SafeVarargs
    public static <T> Collection<T> join(@NonNull Collection<T>... arrays) {
        int size = 0;
        for (Collection<T> array : arrays) {
            size += !isEmpty(array) ? array.size() : 0;
        }

        if (size > 0) {
            ArrayList<T> result = new ArrayList<>(size);

            for (Collection<T> array : arrays) {
                result.addAll(array);
            }

            return result;
        }

        return new ArrayList<>();
    }

    public static <T> boolean isEmpty(@Nullable T[] array) {
        return array == null || array.length == 0;
    }

    public static <T> boolean isEmpty(@Nullable Collection<T> collection) {
        return collection == null || collection.isEmpty();
    }

    public static <T> boolean isNotEmpty(@Nullable Collection<T> collection) {
        return collection != null && !collection.isEmpty();
    }

    public static boolean isEmpty(@Nullable Map map) {
        return map == null || map.isEmpty();
    }

    public static <T> int size(@Nullable T[] array) {
        return array != null ? array.length : 0;
    }

    public static <T> int size(@Nullable Collection<T> collection) {
        return size(collection, null);
    }

    public static <T> int size(@Nullable Collection<T> collection, @Nullable Filter<T> filter) {
        if (collection != null) {
            if (filter != null) {
                int count = 0;
                for (T item : collection) {
                    if (filter.isAccept(item))
                        count++;
                }
                return count;
            }

            return collection.size();
        }

        return 0;
    }

    @Nullable
    public static <T> T getItemByIdx(@NonNull T[] array, int idx) {
        return getItemByIdx(array, idx, null);
    }

    public static <T> boolean hasItemByIdx(@NonNull T[] array, int idx) {
        return !isEmpty(array) && idx >= 0 && idx < array.length;
    }

    public static <T> T getItemByIdx(@NonNull T[] array, int idx, T defValue) {
        if (!isEmpty(array)) {
            if (idx >= 0 && idx < array.length) {
                return array[idx];
            }
        }

        return defValue;
    }

    public static <T> T getItemByIdx(@Nullable List<T> array, int idx, T defValue) {
        if (!isEmpty(array)) {
            if (idx >= 0 && idx < array.size()) {
                return array.get(idx);
            }
        }

        return defValue;
    }

    @SafeVarargs
    public static <T> boolean contains(@NonNull T item, @NonNull T... array) {
        return contains(array, item);
    }

    public static <T> boolean contains(@NonNull T[] array, @NonNull T item) {
        if (!isEmpty(array)) {
            for (T checkItem : array) {
                if (item.equals(checkItem)) {
                    return true;
                }
            }
        }

        return false;
    }

    public static <T> boolean contains(@NonNull T[] array, @NonNull T item, @NonNull Comparator<? super T> c) {
        if (!isEmpty(array)) {
            for (T checkItem : array) {
                if (c.compare(item, checkItem) == 0) {
                    return true;
                }
            }
        }

        return false;
    }

    public static <T> boolean contains(@NonNull Collection<T> collection, @NonNull T item) {
        if (!isEmpty(collection)) {
            for (T checkItem : collection) {
                if (item.equals(checkItem)) {
                    return true;
                }
            }
        }

        return false;
    }

    public static <T> boolean contains(@NonNull Collection<T> collection, @NonNull T item, @NonNull Comparator<? super T> c) {
        if (!isEmpty(collection)) {
            for (T checkItem : collection) {
                if (c.compare(item, checkItem) == 0) {
                    return true;
                }
            }
        }

        return false;
    }

    @Nullable
    @SuppressWarnings("unchecked")
    public static <T> T[] toArray(@Nullable Collection<T> collection) {
        if (!isEmpty(collection)) {
            Class<T> arrayType = (Class<T>) collection.iterator().next().getClass();
            return toArray(collection, arrayType);
        }
        return null;
    }

    @NonNull
    @SuppressWarnings("unchecked")
    public static <T> T[] toArray(@NonNull Collection<T> collection, @NonNull Class<T> itemClassType) {
        return collection.toArray((T[]) Array.newInstance(itemClassType, collection.size()));
    }

    @SafeVarargs
    @NonNull
    public static <T> ArrayList<T> toArrayList(@NonNull T... array) {
        return new ArrayList<>(Arrays.asList(array));
    }

    @NonNull
    public static ArrayList<Byte> toArrayList(@NonNull byte[] array) {
        ArrayList<Byte> result = new ArrayList<>(array.length);
        for (byte b : array) {
            result.add(b);
        }
        return result;
    }

    @NonNull
    public static <T> ArrayList<T> toArrayList(@NonNull Collection<T> collection, @NonNull Class<T> itemClassType) {
        return new ArrayList<>(Arrays.asList(toArray(collection, itemClassType)));
    }

    @NonNull
    public static <T> HashSet<T> toHashSet(@NonNull T[] array) {
        return new HashSet<>(Arrays.asList(array));
    }

    @NonNull
    public static <T> HashSet<T> toHashSet(@NonNull List<T> list) {
        return new HashSet<>(list);
    }

    public static <T> boolean equals(@Nullable Collection<T> collection1, @Nullable Collection<T> collection2) {
        return equals(collection1, collection2, null);
    }

    public static <T> boolean equals(@Nullable Collection<T> collection1, @Nullable Collection<T> collection2, @Nullable Comparator<T> comparator) {
        if (collection1 == collection2) {
            return true;
        }

        if (isEmpty(collection1) && isEmpty(collection2)) {
            return true;
        }

        if (isEmpty(collection1) != isEmpty(collection2)) {
            return false;
        }

        if (collection1 != null && collection1.equals(collection2)) {
            return true;
        }

        if (comparator != null && collection1.size() == collection2.size()) {
            Iterator<T> iterator1 = collection1.iterator();
            Iterator<T> iterator2 = collection1.iterator();
            while (iterator1.hasNext() && iterator2.hasNext()) {
                if (comparator.compare(iterator1.next(), iterator2.next()) != 0) {
                    return false;
                }
            }
            return true;
        }

        return false;
    }

    @Nullable
    @SuppressWarnings("unchecked")
    public static <T> T[] subArray(T[] array, int startIndexInclusive, int endIndexExclusive) {
        if (array == null) {
            return null;
        }
        if (startIndexInclusive < 0) {
            startIndexInclusive = 0;
        }
        if (endIndexExclusive > array.length) {
            endIndexExclusive = array.length;
        }
        int newSize = endIndexExclusive - startIndexInclusive;
        Class<?> type = array.getClass().getComponentType();
        if (newSize <= 0) {
            return (T[]) Array.newInstance(type, 0);
        }
        T[] subarray = (T[]) Array.newInstance(type, newSize);
        System.arraycopy(array, startIndexInclusive, subarray, 0, newSize);
        return subarray;
    }

    @SafeVarargs
    @NonNull
    public static <T> T[] concatArrays(@NonNull T[] first, @NonNull T[]... others) {
        int totalLength = first.length;
        for (T[] array : others) {
            totalLength += array.length;
        }
        T[] result = Arrays.copyOf(first, totalLength);
        int offset = first.length;
        for (T[] array : others) {
            System.arraycopy(array, 0, result, offset, array.length);
            offset += array.length;
        }
        return result;
    }

    public static <T> Collection<T> add(@NonNull Collection<T> list, @NonNull T item) {
        list.add(item);
        return list;
    }

    public static <T> void addAll(@NonNull Collection<T> result, @NonNull T[] array) {
        result.addAll(Arrays.asList(array));
    }

    @SafeVarargs
    public static <T> void addAll(@NonNull Collection<T> result, @NonNull Collection<T>... arrays) {
        for (Collection<T> array : arrays) {
            if (!isEmpty(array)) {
                result.addAll(array);
            }
        }
    }

    public static <T> int indexOf(@NonNull T item, @NonNull Collection<T> list) {
        int index = 0;
        for (T checkItem : list) {
            if (item.equals(checkItem)) {
                return index;
            }
            index++;
        }

        return -1;
    }

    public static <T> int indexOf(@NonNull T item, @NonNull T[] array) {
        T checkItem;
        for (int i = 0; i < array.length; i++) {
            checkItem = array[i];
            if (item.equals(checkItem)) {
                return i;
            }
        }

        return -1;
    }

    @SafeVarargs
    @NonNull
    public static <T> T[] toArray(@NonNull T... items) {
        return items;
    }

    @NonNull
    public static <T> ArrayList<T> toArrayList(@NonNull Collection<T> collection) {
        return new ArrayList<>(collection);
    }

    @NonNull
    public static <T> ArrayList<T> toArrayList(@NonNull T item) {
        return toArrayList(toArray(item));
    }

    @NonNull
    public static <T> ArrayList<T> toArrayList(@NonNull Iterator<T> iterator) {
        ArrayList<T> res = new ArrayList<>(16);
        while (iterator.hasNext()) {
            res.add(iterator.next());
        }
        return res;
    }

    @NonNull
    public static <T> ArrayList<T> toArrayList(@NonNull SparseArray<T> array) {
        ArrayList<T> arrayList = new ArrayList<>(array.size());
        for (int i = 0; i < array.size(); i++)
            arrayList.add(array.valueAt(i));
        return arrayList;
    }

    @NonNull
    public static <T> HashSet<T> toHashSet(@NonNull T item) {
        return new HashSet<>(Arrays.asList(toArray(item)));
    }

    @Nullable
    public static <T> T getFirstItem(@NonNull List<T> list) {
        if (!isEmpty(list)) {
            return list.get(0);
        }

        return null;
    }

    public static <T> boolean isFirstItem(@NonNull List<T> list, T item) {
        if (!isEmpty(list)) {
            return list.get(0) == item;
        }

        return false;
    }

    @Nullable
    public static <T> T getLastItem(@NonNull List<T> list) {
        if (!isEmpty(list)) {
            return list.get(list.size() - 1);
        }

        return null;
    }

    public static <T> boolean isLastItem(@NonNull List<T> list, T item) {
        if (!isEmpty(list)) {
            return list.get(list.size() - 1) == item;
        }

        return false;
    }

    public interface Action<T> {
        void with(@NonNull T item);
    }

    public interface Filter<T> {
        boolean isAccept(@NonNull T item);
    }

    public interface Extractor<T, Z> {
        T getField(@NonNull Z item);
    }

    public interface PairExtractor<K, V> {
        @Nullable
        V getOrNull(@NonNull K key, @NonNull V value);
    }

    public interface Mapper<T, Z> {
        T convert(@NonNull Z item);

    }

    @NonNull
    public static <T> ArrayList<T> filteredArray(@NonNull Collection<T> collection, @NonNull Filter<T> filter) {
        ArrayList<T> result = new ArrayList<>(collection.size());
        for (T item : collection) {
            if (filter.isAccept(item)) {
                result.add(item);
            }
        }
        return result;
    }

    public static <T> void divideArray(@NonNull Collection<T> collection, @NonNull Filter<T> filter,
                                       @NonNull Collection<T> resultAccepted, @NonNull Collection<T> resultRejected) {
        for (T item : collection) {
            if (filter.isAccept(item)) {
                resultAccepted.add(item);
            } else {
                resultRejected.add(item);
            }
        }
    }

    @Nullable
    public static <T> T findFirst(@NonNull Collection<T> collection, @NonNull Filter<T> filter) {
        for (T item : collection) {
            if (filter.isAccept(item)) {
                return item;
            }
        }
        return null;
    }

    public static <T> void forEach(@NonNull Collection<T> collection, @NonNull Action<T> action) {
        for (T item : collection) {
            action.with(item);
        }
    }

    @NonNull
    public static <T, Z> ArrayList<T> convert(@NonNull Collection<Z> collection, @NonNull Mapper<T, Z> mapper) {
        ArrayList<T> result = new ArrayList<>(collection.size());
        for (Z item : collection) {
            result.add(mapper.convert(item));
        }
        return result;
    }

    @NonNull
    public static <T, Z> ArrayList<T> convert(@NonNull Z[] collection, @NonNull Mapper<T, Z> mapper) {
        ArrayList<T> result = new ArrayList<>(collection.length);
        for (Z item : collection) {
            result.add(mapper.convert(item));
        }
        return result;
    }

    @NonNull
    public static <K, V> ArrayList<V> toArrayList(@NonNull Map<K, V> map, @NonNull PairExtractor<K, V> mapper) {
        ArrayList<V> result = new ArrayList<>(map.size());
        V value;
        for (K key : map.keySet()) {
            value = mapper.getOrNull(key, map.get(key));
            if (value != null) {
                result.add(value);
            }
        }
        return result;
    }

    public static <T> List<List<T>> unlimited(@NonNull final List<T> list, final int limit) {
        List<List<T>> lists = new ArrayList<>();

        int count = list.size() / limit;
        int modCount = list.size() % limit;
        count = modCount > 0 ? count + 1 : count;

        for (int i = 0; i < count; i++) {
            int start = i * limit;
            int end = limit;
            if (i == count - 1 && modCount > 0) {
                end = modCount;
            }
            end += start;

            lists.add(list.subList(start, end));
        }
        return lists;
    }

    public static <T> boolean removeIf(@NonNull final Set<T> set, @NonNull Filter<T> filter) {
        List<T> list = toArrayList(set);
        boolean result = removeIf(list, filter);
        set.clear();
        set.addAll(list);
        return result;
    }

    public static <T> boolean removeIf(@NonNull final List<T> list, @NonNull Filter<T> filter) {
        boolean removed = false;
        for (int i = list.size() - 1; i > -1; i--) {
            if (filter.isAccept(list.get(i))) {
                list.remove(i);
                removed = true;
            }
        }
        return removed;
    }

    public static <T> boolean check(@NonNull final Collection<T> list, @NonNull Filter<T> filter) {
        for (T item : list) {
            if (filter.isAccept(item)) {
                return true;
            }
        }
        return false;
    }

    public static <T> boolean check(@NonNull final List<T> list, @NonNull Filter<T> filter) {
        for (int i = list.size() - 1; i > -1; i--) {
            if (filter.isAccept(list.get(i))) {
                return true;
            }
        }
        return false;
    }

    @Nullable
    public static <T> T getIf(@NonNull final List<T> list, @NonNull Filter<T> filter) {
        for (int i = list.size() - 1; i > -1; i--) {
            if (filter.isAccept(list.get(i))) {
                return list.get(i);
            }
        }
        return null;
    }

    @Nullable
    public static <T, Z> T getKeyIf(@NonNull final Map<T, Z> map, @NonNull Filter<T> filter) {
        for (T key : map.keySet()) {
            if (filter.isAccept(key)) {
                return key;
            }
        }
        return null;
    }

    @Nullable
    public static <T, Z> Z  getValueIf(@NonNull final Map<T, Z> map, @NonNull Filter<T> filter) {
        for (T key : map.keySet()) {
            if (filter.isAccept(key)) {
                return map.get(key);
            }
        }
        return null;
    }

    public static <T> boolean moveToFirst(@NonNull final List<T> list, @NonNull Filter<T> filter) {
        int index = -1;
        for (int i = 0; i < list.size(); i++) {
            if (filter.isAccept(list.get(i))) {
                index = i;
                break;
            }
        }
        if (index > -1) {
            T item = list.get(index);
            list.remove(index);
            list.add(0, item);
            return true;
        }
        return false;
    }

    public static <T> List<T> reverse(@NonNull final List<T> list) {
        List<T> result = new ArrayList<>(list);
        Collections.reverse(result);
        return result;
    }

    public static <T> List<T> limit(@NonNull final List<T> list, int limit) {
        if (list.size() > limit) {
            return new ArrayList<>(list.subList(0, limit));
        }
        return new ArrayList<>(list);
    }

    public static <T, Z> Set<T> getFieldsSet(@NonNull final List<Z> list, @NonNull Extractor<T, Z> extractor) {
        Set<T> fields = new HashSet<>(list.size());
        T field;
        for (Z item : list) {
            field = extractor.getField(item);
            if (field != null) fields.add(field);
        }
        return fields;
    }

    @SuppressWarnings("unchecked")
    public static <T> List<T> sort(@NonNull final List<T> list, Comparator<? super T> c, boolean reverse) {
        // Collections.sort(list, reverse ? Collections.reverseOrder(c) : c); // ToDo: !?
        Collections.sort(list, c);
        if (reverse) Collections.reverse(list);
        return list;
    }

    @NonNull
    public static <T> List<T> removeDuplicates(@NonNull final List<T> list, Comparator<? super T> c) {
        List<T> newList = new ArrayList<>(list.size());
        boolean b;
        for (T item : list) {
            b = false;
            for (T newItem : newList) {
                if (c.compare(item, newItem) == 0) {
                    b = true;
                    break;
                }
            }
            if (!b) {
                newList.add(item);
            }
        }
        return newList;
    }

    @NonNull
    public static <T> List<T> subtract(@NonNull final T[] array, @NonNull final T[] checkArray) {
        List<T> newList = new ArrayList<>(array.length);
        for (T item : array) {
            if (!contains(checkArray, item)) {
                newList.add(item);
            }
        }
        return newList;
    }

    @NonNull
    public static <T> List<T> subtract(@NonNull final List<T> list, @NonNull final List<T> checkList) {
        return subtract(list, checkList, null);
    }

    @NonNull
    public static <T> List<T> subtract(@NonNull final List<T> list, @NonNull final List<T> checkList, @Nullable Comparator<? super T> c) {
        List<T> newList = new ArrayList<>(list.size());
        for (T item : list) {
            if (!contains(checkList, item, c)) {
                newList.add(item);
            }
        }
        return newList;
    }

    public static <T> int hashCodes(@NonNull final Collection<T> list) {
        return Arrays.hashCode(toArray(list));
    }

}