import { useState, useEffect, useRef } from 'react';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { ScrollArea } from '@/components/ui/scroll-area';
import { Avatar, AvatarFallback } from '@/components/ui/avatar';
import { Alert, AlertDescription } from '@/components/ui/alert';
import {
  Loader2,
  Send,
  Plus,
  LogOut,
  FileText,
  X,
  Menu,
  ChevronLeft,
} from 'lucide-react';

const API_BASE_URL = 'https://ngmchatbot.onrender.com';

interface Message {
  id: string;
  role: 'user' | 'AI';
  message: string;
  created_at: string;
}

interface Chat {
  id: string;
  title: string;
  user_id?: string;
  created_at: string;
  conversations: Message[];
}

interface UserData {
  id: string;
  userName: string;
  email: string;
}

interface ChatInterfaceProps {
  onLogout: () => void;
  userData: UserData;
  onUpdateUserData: (userData: UserData) => void;
}

export default function ChatInterface({
  onLogout,
  userData,
  onUpdateUserData,
}: ChatInterfaceProps) {
  const [chats, setChats] = useState<Chat[]>([]);
  const [currentChat, setCurrentChat] = useState<Chat | null>(null);
  const [message, setMessage] = useState('');
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState('');
  const [showPdfViewer, setShowPdfViewer] = useState(false);
  const [pdfUrl, setPdfUrl] = useState('');
  const [pdfTitle, setPdfTitle] = useState('');
  const [showSidebar, setShowSidebar] = useState(false);
  const [showDesktopSidebar, setShowDesktopSidebar] = useState(true);
  const [isMobile, setIsMobile] = useState(false);
  const messagesEndRef = useRef<HTMLDivElement>(null);

  const scrollToBottom = () => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  };

  useEffect(() => {
    scrollToBottom();
  }, [currentChat?.conversations]);

  useEffect(() => {
    const checkMobile = () => {
      setIsMobile(window.innerWidth < 768);
    };

    checkMobile();
    window.addEventListener('resize', checkMobile);

    // Load user's specific chats
    loadUserChats();

    return () => window.removeEventListener('resize', checkMobile);
  }, [userData.email]);

  const getAuthHeaders = () => {
    const authKey = localStorage.getItem('ngmc-auth-key');
    return {
      'Content-Type': 'application/json',
      'x-api-key': authKey || '',
    };
  };

  const loadUserChats = async () => {
    try {
      const response = await fetch(`${API_BASE_URL}/getuserchats/`, {
        method: 'POST',
        headers: getAuthHeaders(),
        body: JSON.stringify({
          email: userData.email,
        }),
      });

      if (response.ok) {
        const data = await response.json();
        setChats(data.chats || []);

        // Update user data if we got user info back
        if (data.user && data.user.id && data.user.id !== userData.id) {
          onUpdateUserData({
            id: data.user.id,
            userName: data.user.userName,
            email: data.user.email,
          });
        }
      } else if (response.status === 404) {
        // User not found, will be created on first chat
        setChats([]);
      } else {
        console.error('Failed to load user chats:', response.status);
        setChats([]);
      }
    } catch (error) {
      console.error('Failed to load user chats:', error);
      setChats([]);
    }
  };

  const extractPdfUrls = (
    text: string
  ): Array<{ url: string; title: string }> => {
    const pdfs: Array<{ url: string; title: string }> = [];

    const markdownRegex = /\[([^\]]+)\]\(([^)]+\.pdf)\)/g;
    let match;
    while ((match = markdownRegex.exec(text)) !== null) {
      pdfs.push({
        title: match[1],
        url: match[2],
      });
    }

    const customRegex = /\[([^\]]+)\]$$(https?:\/\/[^)]+\.pdf)$$/g;
    while ((match = customRegex.exec(text)) !== null) {
      pdfs.push({
        title: match[1],
        url: match[2],
      });
    }

    return pdfs;
  };

  const handlePdfClick = (url: string, title: string) => {
    // Only show PDF viewer on desktop
    if (!isMobile) {
      setPdfUrl(url);
      setPdfTitle(title);
      setShowPdfViewer(true);
    } else {
      // On mobile, open PDF in new tab
      window.open(url, '_blank', 'noopener,noreferrer');
    }

    // Close sidebar on mobile when PDF opens
    if (isMobile) {
      setShowSidebar(false);
    }
  };

  const autoOpenPdf = (message: string) => {
    const pdfs = extractPdfUrls(message);
    if (pdfs.length > 0) {
      handlePdfClick(pdfs[0].url, pdfs[0].title);
    }
  };

  const handleSendMessage = async () => {
    if (!message.trim() || isLoading) return;

    const userMessage = message.trim();
    setMessage('');

    // Close sidebar on mobile after sending message
    if (isMobile) {
      setShowSidebar(false);
    }

    const tempUserMessage: Message = {
      id: `temp-${Date.now()}`,
      role: 'user',
      message: userMessage,
      created_at: new Date().toISOString(),
    };

    if (currentChat) {
      setCurrentChat((prev) =>
        prev
          ? {
              ...prev,
              conversations: [...prev.conversations, tempUserMessage],
            }
          : null
      );
    } else {
      const tempChat: Chat = {
        id: `temp-chat-${Date.now()}`,
        title: 'New Chat',
        created_at: new Date().toISOString(),
        conversations: [tempUserMessage],
      };
      setCurrentChat(tempChat);
    }

    setIsLoading(true);
    setError('');

    try {
      const requestBody = {
        message: userMessage,
        userName: userData.userName,
        email: userData.email,
      };

      let response;
      if (currentChat && !currentChat.id.startsWith('temp-chat-')) {
        response = await fetch(`${API_BASE_URL}/postchat/${currentChat.id}/`, {
          method: 'POST',
          headers: getAuthHeaders(),
          body: JSON.stringify(requestBody),
        });
      } else {
        response = await fetch(`${API_BASE_URL}/postchat/`, {
          method: 'POST',
          headers: getAuthHeaders(),
          body: JSON.stringify(requestBody),
        });
      }

      if (response.ok) {
        const data = await response.json();

        // Update user data if userId is returned
        if (data.userId && data.userId !== userData.id) {
          onUpdateUserData({
            ...userData,
            id: data.userId,
          });
        }

        // Reload user's chats to get updated data
        await loadUserChats();

        let updatedChat = null;

        if (!currentChat && data.chatId) {
          // New chat created
          const newChat = chats.find((chat: Chat) => chat.id === data.chatId);
          if (!newChat) {
            // Chat not in current list, reload to get it
            await loadUserChats();
            const updatedChats = chats;
            const foundChat = updatedChats.find(
              (chat: Chat) => chat.id === data.chatId
            );
            if (foundChat) {
              setCurrentChat(foundChat);
              updatedChat = foundChat;
            }
          } else {
            setCurrentChat(newChat);
            updatedChat = newChat;
          }
        } else if (currentChat && !currentChat.id.startsWith('temp-chat-')) {
          // Continuing existing chat
          const refreshedChat = chats.find(
            (chat: Chat) => chat.id === currentChat.id
          );
          if (refreshedChat) {
            setCurrentChat(refreshedChat);
            updatedChat = refreshedChat;
          }
        } else if (
          currentChat &&
          currentChat.id.startsWith('temp-chat-') &&
          data.chatId
        ) {
          // Temp chat got real ID
          const newChat = chats.find((chat: Chat) => chat.id === data.chatId);
          if (newChat) {
            setCurrentChat(newChat);
            updatedChat = newChat;
          }
        }

        // Auto-open PDF if AI message contains one
        if (updatedChat && updatedChat.conversations.length > 0) {
          const latestMessage =
            updatedChat.conversations[updatedChat.conversations.length - 1];
          if (latestMessage.role === 'AI') {
            autoOpenPdf(latestMessage.message);
          }
        }
      } else {
        const errorData = await response.json().catch(() => ({}));
        setError(
          errorData.error || 'Failed to send message. Please try again.'
        );

        // Revert UI changes on error
        if (currentChat) {
          if (currentChat.id.startsWith('temp-chat-')) {
            setCurrentChat(null);
          } else {
            setCurrentChat((prev) =>
              prev
                ? {
                    ...prev,
                    conversations: prev.conversations.filter(
                      (msg) => !msg.id.startsWith('temp-')
                    ),
                  }
                : null
            );
          }
        }
      }
    } catch (error) {
      console.error('Send message failed:', error);
      setError('Network error. Please check your connection.');

      // Revert UI changes on error
      if (currentChat) {
        if (currentChat.id.startsWith('temp-chat-')) {
          setCurrentChat(null);
        } else {
          setCurrentChat((prev) =>
            prev
              ? {
                  ...prev,
                  conversations: prev.conversations.filter(
                    (msg) => !msg.id.startsWith('temp-')
                  ),
                }
              : null
          );
        }
      }
    }

    setIsLoading(false);
  };

  const startNewChat = () => {
    setCurrentChat(null);
    setShowPdfViewer(false);
    setPdfUrl('');
    setPdfTitle('');
    // Close sidebar on mobile when starting new chat
    if (isMobile) {
      setShowSidebar(false);
    }
  };

  const selectChat = (chat: Chat) => {
    setCurrentChat(chat);
    setShowPdfViewer(false);
    setPdfUrl('');
    setPdfTitle('');
    // Close sidebar on mobile when selecting chat
    if (isMobile) {
      setShowSidebar(false);
    }
  };

  const formatText = (text: string) => {
    const lines = text.split('\n');

    return lines.map((line, lineIndex) => {
      const parts = line.split(/(\*\*[^*]+\*\*)/g);

      return (
        <div key={lineIndex} className={lineIndex > 0 ? 'mt-2' : ''}>
          {parts.map((part, partIndex) => {
            if (
              part.startsWith('**') &&
              part.endsWith('**') &&
              part.length > 4
            ) {
              const boldText = part.slice(2, -2);
              return (
                <strong key={partIndex} className="font-semibold">
                  {boldText}
                </strong>
              );
            }
            return part;
          })}
        </div>
      );
    });
  };

  const renderMessage = (msg: Message) => {
    if (msg.role === 'AI') {
      const markdownLinkRegex = /\[([^\]]+)\]\(([^)]+)\)/g;
      const parts = [];
      let lastIndex = 0;
      let match;

      while ((match = markdownLinkRegex.exec(msg.message)) !== null) {
        if (match.index > lastIndex) {
          const textBefore = msg.message.slice(lastIndex, match.index);
          parts.push({ type: 'text', content: textBefore });
        }

        const title = match[1];
        const url = match[2];
        const isPdf = url.toLowerCase().includes('.pdf');

        parts.push({
          type: 'link',
          title: title,
          url: url,
          isPdf: isPdf,
        });

        lastIndex = match.index + match[0].length;
      }

      if (lastIndex < msg.message.length) {
        const textAfter = msg.message.slice(lastIndex);
        parts.push({ type: 'text', content: textAfter });
      }

      if (parts.length === 0) {
        parts.push({ type: 'text', content: msg.message });
      }

      return (
        <div className="text-sm leading-relaxed">
          {parts.map((part, index) => {
            if (part.type === 'link') {
              if (part.isPdf) {
                return (
                  <div key={index} className="inline-block w-full">
                    <Button
                      variant="link"
                      className="text-blue-500 hover:text-blue-400 underline p-0 h-auto font-normal text-sm text-left whitespace-normal break-words max-w-full"
                      onClick={() => handlePdfClick(part.url, part.title)}
                      style={{
                        wordBreak: 'break-word',
                        overflowWrap: 'break-word',
                        whiteSpace: 'normal',
                        display: 'inline-block',
                        width: 'auto',
                        maxWidth: '100%',
                      }}>
                      {part.title}
                    </Button>
                  </div>
                );
              } else {
                return (
                  <div key={index} className="inline-block w-full">
                    <Button
                      variant="link"
                      className="text-blue-500 hover:text-blue-400 underline p-0 h-auto font-normal text-sm text-left whitespace-normal break-words max-w-full"
                      onClick={() =>
                        window.open(part.url, '_blank', 'noopener,noreferrer')
                      }
                      style={{
                        wordBreak: 'break-word',
                        overflowWrap: 'break-word',
                        whiteSpace: 'normal',
                        display: 'inline-block',
                        width: 'auto',
                        maxWidth: '100%',
                      }}>
                      {part.title}
                    </Button>
                  </div>
                );
              }
            } else {
              const lines = part.content.split('\n');
              return (
                <span key={index}>
                  {lines.map((line, lineIndex) => {
                    const boldParts = line.split(/(\*\*[^\*]+\*\*)/g);
                    return (
                      <span key={lineIndex}>
                        {lineIndex > 0 && <br />}
                        {boldParts.map((boldPart, boldIndex) => {
                          if (
                            boldPart.startsWith('**') &&
                            boldPart.endsWith('**') &&
                            boldPart.length > 4
                          ) {
                            const boldText = boldPart.slice(2, -2);
                            return (
                              <strong key={boldIndex} className="font-semibold">
                                {boldText}
                              </strong>
                            );
                          }
                          return boldPart;
                        })}
                      </span>
                    );
                  })}
                </span>
              );
            }
          })}
        </div>
      );
    }

    return (
      <div className="text-sm leading-relaxed">{formatText(msg.message)}</div>
    );
  };

  return (
    <div className="flex h-screen bg-background text-foreground">
      {/* Mobile overlay for sidebar */}
      {showSidebar && isMobile && (
        <div
          className="fixed inset-0 bg-black bg-opacity-50 z-40"
          onClick={() => setShowSidebar(false)}
        />
      )}

      {/* Sidebar - Original PC design maintained */}
      {(showDesktopSidebar || showSidebar) && (
        <div
          className={`
          w-64 bg-sidebar border-r border-sidebar-border flex flex-col h-screen
          ${isMobile ? 'fixed z-50' : 'relative'}
          ${isMobile && showSidebar ? 'translate-x-0' : ''}
          ${isMobile && !showSidebar ? '-translate-x-full' : ''}
          transition-transform duration-300 ease-in-out
        `}>
          {/* Desktop close button */}
          {!isMobile && (
            <div className="p-2 flex justify-end">
              <Button
                onClick={() => setShowDesktopSidebar(false)}
                variant="ghost"
                size="sm"
                className="h-8 w-8 p-0">
                <ChevronLeft className="h-4 w-4" />
              </Button>
            </div>
          )}

          <div className="p-4 border-b border-sidebar-border flex-shrink-0">
            <div className="flex items-center gap-3 mb-4">
              <img
                src="https://www.ngmc.org/wp-content/uploads/2024/08/logoblue.png"
                alt="NGMC Logo"
                className="h-8 w-auto"
              />
              <div className="text-sm font-medium text-sidebar-foreground">
                NGMC Chat
              </div>
            </div>
            <Button
              onClick={startNewChat}
              className="w-full justify-start gap-2 bg-transparent"
              variant="outline">
              <Plus className="h-4 w-4" />
              New chat
            </Button>
          </div>

          <div className="flex-1 min-h-0 overflow-hidden">
            <ScrollArea className="h-full p-2">
              <div className="space-y-1">
                {chats.map((chat) => (
                  <Button
                    key={chat.id}
                    onClick={() => selectChat(chat)}
                    variant={
                      currentChat?.id === chat.id ? 'secondary' : 'ghost'
                    }
                    className="w-full justify-start text-left h-auto p-3">
                    <div className="truncate text-sm">{chat.title}</div>
                  </Button>
                ))}
              </div>
            </ScrollArea>
          </div>

          {/* Profile section - Fixed at bottom */}
          <div className="p-4 border-t border-sidebar-border flex-shrink-0 mt-auto">
            <div className="flex items-center gap-3">
              <Avatar className="h-8 w-8">
                <AvatarFallback className="bg-sidebar-primary text-sidebar-primary-foreground text-sm">
                  {userData.userName.charAt(0).toUpperCase()}
                </AvatarFallback>
              </Avatar>
              <div className="flex-1 min-w-0">
                <div className="text-sm font-medium text-sidebar-foreground truncate">
                  {userData.userName}
                </div>
                <div className="text-xs text-sidebar-muted-foreground truncate">
                  {userData.email}
                </div>
              </div>
              <Button
                onClick={onLogout}
                variant="ghost"
                size="sm"
                className="h-8 w-8 p-0">
                <LogOut className="h-4 w-4" />
              </Button>
            </div>
          </div>
        </div>
      )}

      {/* Main content area */}
      <div
        className={`flex-1 flex flex-col ${
          showPdfViewer && !isMobile ? 'w-1/2' : ''
        }`}>
        {/* Header for both mobile and desktop when sidebar is hidden */}
        {(isMobile || !showDesktopSidebar) && (
          <div className="flex items-center justify-between p-3 md:p-4 border-b border-border bg-background flex-shrink-0">
            <Button
              onClick={() => {
                if (isMobile) {
                  setShowSidebar(true);
                } else {
                  setShowDesktopSidebar(true);
                }
              }}
              variant="ghost"
              size="sm"
              className="h-8 w-8 p-0">
              <Menu className="h-4 w-4" />
            </Button>
            <div className="flex items-center gap-2">
              <img
                src="https://www.ngmc.org/wp-content/uploads/2024/08/logoblue.png"
                alt="NGMC Logo"
                className="h-6 w-auto"
              />
              <div className="text-sm font-medium">NGMC Chat</div>
            </div>
            <div className="w-8"></div> {/* Spacer for centering */}
          </div>
        )}

        {/* Messages area */}
        <div className="flex-1 overflow-hidden">
          <ScrollArea className="h-full p-4">
            {currentChat ? (
              <div
                className={`space-y-6 max-w-3xl mx-auto ${
                  isMobile ? 'pb-20' : 'pb-4'
                }`}>
                {currentChat.conversations
                  .filter((msg) => !msg.id.startsWith('temp-'))
                  .map((msg) => (
                    <div
                      key={msg.id}
                      className={`flex gap-4 ${
                        msg.role === 'user' ? 'flex-row-reverse' : ''
                      }`}>
                      <Avatar className="h-8 w-8 mt-1 flex-shrink-0">
                        <AvatarFallback
                          className={
                            msg.role === 'user'
                              ? 'bg-primary text-primary-foreground'
                              : 'bg-muted'
                          }>
                          {msg.role === 'user'
                            ? userData.userName.charAt(0).toUpperCase()
                            : 'AI'}
                        </AvatarFallback>
                      </Avatar>
                      <div
                        className={`flex-1 space-y-2 ${
                          msg.role === 'user' ? 'text-right' : ''
                        }`}>
                        <div
                          className={`inline-block max-w-[80%] p-3 rounded-lg ${
                            msg.role === 'user'
                              ? 'bg-primary text-primary-foreground ml-auto'
                              : 'bg-muted'
                          }`}>
                          {renderMessage(msg)}
                        </div>
                      </div>
                    </div>
                  ))}
                {currentChat.conversations.some((msg) =>
                  msg.id.startsWith('temp-')
                ) && (
                  <>
                    {currentChat.conversations
                      .filter((msg) => msg.id.startsWith('temp-'))
                      .map((msg) => (
                        <div
                          key={msg.id}
                          className="flex gap-4 flex-row-reverse">
                          <Avatar className="h-8 w-8 mt-1 flex-shrink-0">
                            <AvatarFallback className="bg-primary text-primary-foreground">
                              {userData.userName.charAt(0).toUpperCase()}
                            </AvatarFallback>
                          </Avatar>
                          <div className="flex-1 space-y-2 text-right">
                            <div className="inline-block max-w-[80%] p-3 rounded-lg bg-primary text-primary-foreground ml-auto">
                              <div className="text-sm leading-relaxed">
                                {renderMessage(msg)}
                              </div>
                            </div>
                          </div>
                        </div>
                      ))}
                    {isLoading && (
                      <div className="flex gap-4">
                        <Avatar className="h-8 w-8 mt-1 flex-shrink-0">
                          <AvatarFallback className="bg-muted">
                            AI
                          </AvatarFallback>
                        </Avatar>
                        <div className="flex-1 space-y-2">
                          <div className="inline-block bg-muted p-3 rounded-lg">
                            <div className="flex items-center gap-2 text-muted-foreground">
                              <Loader2 className="h-4 w-4 animate-spin" />
                              <span className="text-sm">Thinking...</span>
                            </div>
                          </div>
                        </div>
                      </div>
                    )}
                  </>
                )}
                {!currentChat.conversations.some((msg) =>
                  msg.id.startsWith('temp-')
                ) &&
                  isLoading && (
                    <div className="flex gap-4">
                      <Avatar className="h-8 w-8 mt-1 flex-shrink-0">
                        <AvatarFallback className="bg-muted">AI</AvatarFallback>
                      </Avatar>
                      <div className="flex-1 space-y-2">
                        <div className="inline-block bg-muted p-3 rounded-lg">
                          <div className="flex items-center gap-2 text-muted-foreground">
                            <Loader2 className="h-4 w-4 animate-spin" />
                            <span className="text-sm">Thinking...</span>
                          </div>
                        </div>
                      </div>
                    </div>
                  )}
                <div ref={messagesEndRef} />
              </div>
            ) : (
              <div className="flex items-center justify-center h-full">
                <div className="text-center space-y-4">
                  <div className="text-4xl font-semibold text-muted-foreground">
                    Welcome to NGMC Chat
                  </div>
                  <div className="text-lg text-muted-foreground">
                    How can I help you today?
                  </div>
                </div>
              </div>
            )}
          </ScrollArea>
        </div>

        {/* Input area - Fixed at bottom on mobile, normal on desktop */}
        <div
          className={`
          p-4 border-t border-border bg-background flex-shrink-0
          ${isMobile ? 'fixed bottom-0 left-0 right-0 z-30' : ''}
        `}>
          <div className="max-w-3xl mx-auto">
            {error && (
              <Alert variant="destructive" className="mb-4">
                <AlertDescription>{error}</AlertDescription>
              </Alert>
            )}
            <div className="flex gap-2">
              <Input
                value={message}
                onChange={(e) => setMessage(e.target.value)}
                placeholder="Ask anything..."
                onKeyDown={(e) => {
                  if (e.key === 'Enter' && !e.shiftKey) {
                    e.preventDefault();
                    handleSendMessage();
                  }
                }}
                disabled={isLoading}
                className="flex-1"
              />
              <Button
                onClick={handleSendMessage}
                disabled={isLoading || !message.trim()}
                size="icon">
                {isLoading ? (
                  <Loader2 className="h-4 w-4 animate-spin" />
                ) : (
                  <Send className="h-4 w-4" />
                )}
              </Button>
            </div>
          </div>
        </div>
      </div>

      {/* PDF Viewer - Desktop only */}
      {showPdfViewer && !isMobile && (
        <div className="w-1/2 border-l border-border bg-card flex flex-col">
          <div className="p-4 border-b border-border flex items-center justify-between flex-shrink-0">
            <div className="flex items-center gap-2">
              <FileText className="h-4 w-4" />
              <span className="text-sm font-medium">
                {pdfTitle || 'PDF Document'}
              </span>
            </div>
            <Button
              onClick={() => setShowPdfViewer(false)}
              variant="ghost"
              size="sm"
              className="h-8 w-8 p-0">
              <X className="h-4 w-4" />
            </Button>
          </div>
          <div className="flex-1 overflow-hidden">
            <iframe
              src={pdfUrl}
              className="w-full h-full border-0"
              title="PDF Document"
              onError={() =>
                setError(
                  'Failed to load PDF. Please check if the URL is accessible.'
                )
              }
            />
          </div>
        </div>
      )}
    </div>
  );
}
