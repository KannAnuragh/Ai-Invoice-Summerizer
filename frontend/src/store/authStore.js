import { create } from 'zustand';
import { persist } from 'zustand/middleware';

const useAuthStore = create(
  persist(
    (set) => ({
      user: null,
      token: null,
      isAuthenticated: false,
      
      login: (user, token) => {
        set({ user, token, isAuthenticated: true });
        localStorage.setItem('auth_token', token);
      },
      
      logout: () => {
        set({ user: null, token: null, isAuthenticated: false });
        localStorage.removeItem('auth_token');
      },
      
      updateUser: (user) => set({ user }),
    }),
    {
      name: 'auth-storage',
    }
  )
);

export default useAuthStore;
