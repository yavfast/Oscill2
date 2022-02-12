package com.oscill.types;

import androidx.annotation.NonNull;

import java.util.AbstractList;
import java.util.Arrays;
import java.util.List;

public class ArrayListEx<E> extends AbstractList<E> {

    protected int size = 0;
    protected Object[] elements;

    public ArrayListEx(int capacity) {
        super();
        elements = new Object[capacity];
    }

    public void setCapacity(int capacity) {
        if (size() < capacity) {
            elements = Arrays.copyOf(elements, capacity);
        }
    }

    @Override
    public E get(int index) {
        return (E) elements[index];
    }

    @Override
    public boolean add(E element) {
        elements[size++] = element;
        return true;
    }

    @Override
    public void add(int index, E element) {
        elements[index] = element;
    }

    @Override
    public int size() {
        return elements.length;
    }

    private static class SubList<E> extends ArrayListEx<E> {
        private int offset = 0;

        public SubList(@NonNull ArrayListEx<E> parent, int fromIndex, int toIndex) {
            super(0);
            this.elements = parent.elements;
            this.offset = fromIndex;
            this.size = toIndex - fromIndex;
        }

        @Override
        public E get(int index) {
            return (E) elements[index + offset];
        }

    }

    @NonNull
    @Override
    public List<E> subList(int fromIndex, int toIndex) {
        return new SubList<>(this, fromIndex, toIndex);
    }
}
