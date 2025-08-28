'use client';

import type React from 'react';

import { useState, useEffect } from 'react';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from '@/components/ui/card';
import { Label } from '@/components/ui/label';
import { Alert, AlertDescription } from '@/components/ui/alert';
import { Loader2 } from 'lucide-react';
import ChatInterface from '@/components/chat-interface';

const API_BASE_URL = 'https://ngmchatbot.onrender.com';

export default function Home() {
  const [isAuthenticated, setIsAuthenticated] = useState(false);
  const [isLoading, setIsLoading] = useState(true);
  const [loginData, setLoginData] = useState({
    userName: '',
    email: '',
    password: '',
    accessKey: '',
  });
  const [loginLoading, setLoginLoading] = useState(false);
  const [error, setError] = useState('');

  // Check if user is already authenticated
  useEffect(() => {
    const checkAuth = async () => {
      const storedUserName = localStorage.getItem('ngmc-user-name');
      const storedEmail = localStorage.getItem('ngmc-user-email');
      const storedPassword = localStorage.getItem('ngmc-password');
      const storedAccessKey = localStorage.getItem('ngmc-access-key');

      if (storedUserName && storedEmail && storedPassword && storedAccessKey) {
        try {
          const response = await fetch(`${API_BASE_URL}/checkAuth/`, {
            method: 'POST',
            headers: {
              'Content-Type': 'application/json',
            },
            body: JSON.stringify({
              apikey: storedAccessKey, // Use stored access key as API key
              userName: storedUserName,
              email: storedEmail,
              password: storedPassword,
            }),
          });

          if (response.ok) {
            const data = await response.json();
            if (data.status === 'success') {
              setIsAuthenticated(true);
            } else {
              // Clear invalid stored data
              clearStoredAuth();
            }
          } else {
            clearStoredAuth();
          }
        } catch (error) {
          console.error('Auth check failed:', error);
          clearStoredAuth();
        }
      }
      setIsLoading(false);
    };

    checkAuth();
  }, []);

  const clearStoredAuth = () => {
    localStorage.removeItem('ngmc-user-name');
    localStorage.removeItem('ngmc-user-email');
    localStorage.removeItem('ngmc-password');
    localStorage.removeItem('ngmc-access-key');
  };

  const handleLogin = async (e: React.FormEvent) => {
    e.preventDefault();
    setLoginLoading(true);
    setError('');

    // Validate all fields are filled
    if (
      !loginData.userName.trim() ||
      !loginData.email.trim() ||
      !loginData.password.trim() ||
      !loginData.accessKey.trim()
    ) {
      setError('All fields are required');
      setLoginLoading(false);
      return;
    }

    try {
      const response = await fetch(`${API_BASE_URL}/checkAuth/`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({
          apikey: loginData.accessKey, // Use access key as API key
          userName: loginData.userName,
          email: loginData.email,
          password: loginData.password,
        }),
      });

      if (response.ok) {
        const data = await response.json();
        if (data.status === 'success') {
          // Store auth data in localStorage on success
          localStorage.setItem('ngmc-user-name', loginData.userName);
          localStorage.setItem('ngmc-user-email', loginData.email);
          localStorage.setItem('ngmc-password', loginData.password);
          localStorage.setItem('ngmc-access-key', loginData.accessKey);

          setIsAuthenticated(true);
        } else {
          setError(data.message || 'Authentication failed');
        }
      } else {
        const errorData = await response.json();
        setError(
          errorData.error ||
            'Authentication failed. Please check your credentials.'
        );
      }
    } catch (error) {
      console.error('Login failed:', error);
      setError('Login failed. Please check your connection and try again.');
    }

    setLoginLoading(false);
  };

  const handleLogout = () => {
    clearStoredAuth();
    setIsAuthenticated(false);
    setLoginData({
      userName: '',
      email: '',
      password: '',
      accessKey: '',
    });
  };

  // Get stored auth data for chat interface
  const getStoredAuthData = () => {
    return {
      apikey: localStorage.getItem('ngmc-access-key') || '', // Use access key as API key
      userName: localStorage.getItem('ngmc-user-name') || '',
      email: localStorage.getItem('ngmc-user-email') || '',
      password: localStorage.getItem('ngmc-password') || '',
    };
  };

  if (isLoading) {
    return (
      <div className="min-h-screen bg-background flex items-center justify-center">
        <Loader2 className="h-8 w-8 animate-spin text-muted-foreground" />
      </div>
    );
  }

  if (!isAuthenticated) {
    return (
      <div className="min-h-screen bg-background flex items-center justify-center p-4">
        <Card className="w-full max-w-md">
          <CardHeader className="text-center">
            <div className="flex justify-center mb-4">
              <img
                src="https://www.ngmc.org/wp-content/uploads/2024/08/logoblue.png"
                alt="NGMC Logo"
                className="h-16 w-auto"
              />
            </div>
            <CardTitle className="text-2xl font-semibold">
              Welcome to NGMC Chat
            </CardTitle>
            <CardDescription>
              Nallamuthu Gounder Mahalingam College
              <br />
              Pollachi, Coimbatore District, Tamil Nadu
            </CardDescription>
          </CardHeader>
          <CardContent>
            <form onSubmit={handleLogin} className="space-y-4">
              <div className="space-y-2">
                <Label htmlFor="userName">Full Name</Label>
                <Input
                  id="userName"
                  type="text"
                  placeholder="Enter your full name"
                  value={loginData.userName}
                  onChange={(e) =>
                    setLoginData((prev) => ({
                      ...prev,
                      userName: e.target.value,
                    }))
                  }
                  disabled={loginLoading}
                />
              </div>
              <div className="space-y-2">
                <Label htmlFor="email">Email</Label>
                <Input
                  id="email"
                  type="email"
                  placeholder="Enter your email"
                  value={loginData.email}
                  onChange={(e) =>
                    setLoginData((prev) => ({ ...prev, email: e.target.value }))
                  }
                  disabled={loginLoading}
                />
              </div>
              <div className="space-y-2">
                <Label htmlFor="password">Password</Label>
                <Input
                  id="password"
                  type="password"
                  placeholder="Enter your password"
                  value={loginData.password}
                  onChange={(e) =>
                    setLoginData((prev) => ({
                      ...prev,
                      password: e.target.value,
                    }))
                  }
                  disabled={loginLoading}
                />
              </div>
              <div className="space-y-2">
                <Label htmlFor="accessKey">Access Key</Label>
                <Input
                  id="accessKey"
                  type="password"
                  placeholder="Enter your access key"
                  value={loginData.accessKey}
                  onChange={(e) =>
                    setLoginData((prev) => ({
                      ...prev,
                      accessKey: e.target.value,
                    }))
                  }
                  disabled={loginLoading}
                />
              </div>
              {error && (
                <Alert variant="destructive">
                  <AlertDescription>{error}</AlertDescription>
                </Alert>
              )}

              <Button type="submit" className="w-full" disabled={loginLoading}>
                {loginLoading ? (
                  <>
                    <Loader2 className="mr-2 h-4 w-4 animate-spin" />
                    Signing in...
                  </>
                ) : (
                  'Sign in'
                )}
              </Button>
            </form>
          </CardContent>
        </Card>
      </div>
    );
  }

  return (
    <ChatInterface onLogout={handleLogout} authData={getStoredAuthData()} />
  );
}
