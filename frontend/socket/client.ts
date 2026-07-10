import { io, Socket } from "socket.io-client";

let socket: Socket | undefined;

export function getSocket() {
  if (!socket) {
    socket = io(process.env.NEXT_PUBLIC_SOCKET_URL ?? "http://localhost:8000", {
      autoConnect: false,
      transports: ["websocket"]
    });
  }

  return socket;
}
