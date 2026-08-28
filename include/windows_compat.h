#pragma once
#ifndef _WINDOWS_COMPAT_H_
#define _WINDOWS_COMPAT_H_

#ifdef _WIN32
  #define WIN32_LEAN_AND_MEAN
  #include <windows.h>
  #include <winsock2.h>
  #include <ws2tcpip.h>
#else
  #include <cstdint>
  #include <cstddef>
  #include <cstring>
  #include <sys/socket.h>
  #include <netinet/in.h>
  #include <arpa/inet.h>
  #include <unistd.h>

  typedef void* HWND;
  #define __declspec(x)
  #define __cdecl
  #define closesocket close
  typedef int SOCKET;
  #define INVALID_SOCKET (-1)
  #define SOCKET_ERROR (-1)
#endif

#endif // _WINDOWS_COMPAT_H_
