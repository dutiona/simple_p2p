# Simple P2P messaging program

The program is built in two parts: client.py and server.py
They are built using minimal dependencies to standard asyncio and json.

This P2P messaging program has a server maintaining and giving a list of active clients, and the client which is
communicating with the server as well as other clients to send/receive their messages.

## Server

The server only maintain a list of the client that declared themselves.
It supports sending the list of active clients if requested.

Also, in order to maintain the list of active clients, it will regularly perform a ping, to which clients must respond
pong.

## Client

The client is built in three parts:

* the startup/handshake routine with the server to get the list of active clients
* the local server listening and receiving messages from other clients
* the messaging routine actually sending messages to the other clients

## Resilience

Some resilience is implemented:

* the server can go offline and online again, it will regenerate its client list from the active clients
* a client can go offline and online again (or not), it will be dropped from the active client list by the server, and
  the other clients support recovering from a failed delivered message.

## Not implemented

* The message is a fixed string
* Scaling is to be tested more in-depth
* Messages are not crypted (TLS would be preferred)
* The server should provide checksum to clients to verify the integrity of messages received.
* Refactoring is much needed
* Decorelate the requesting the client list and messaging routine that are currently in the same loop
* Maybe support having several server providing client list (communicating together for merging/regenerating if one went offline?)
* Other stuff... This is really a simple program
