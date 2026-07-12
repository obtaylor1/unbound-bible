import { createContext, useContext } from 'react'

export const AuthContext = createContext({ user: null, status: 'anonymous' })
export const useAuth = () => useContext(AuthContext)
