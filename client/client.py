import asyncio
import json

# Message format
# {"request" : "<func>", [optional "infos" : { ... }]}
# Response format
# {"response" : "<code>", [optional "infos" : { ... }]}


# Handshake with server
async def handshake(reader, writer):
    # handshake the server
    message = {"request": "handshake", "infos": {
        "ip": self_ip, "port": self_port}}
    writer.write(json.dumps(message).encode())

    # Waiting for OK from server
    data_encoded = await reader.read(1024)
    decoded_data = json.loads(data_encoded.decode())

    try:
        # Server response is OK
        if decoded_data["response"] == "OK":
            return True
        else:
            print("Server KO: <{}>".format(decoded_data["infos"]))
    except KeyError:
        print("Invalid response: <{}>".format(data_encoded.decode()))
        return False


# Try to do the handshake multiple time
async def do_handshake(reader, writer, max_retry_count, time_between_retry):
    ret = await handshake(reader, writer)
    try_count = 1
    while not ret and try_count < max_retry_count:
        print("Could not contact server...")
        await asyncio.sleep(1)
        print("Retrying...")
        ret = await handshake()
        try_count += 1

    return ret


# Request the client list from the server
async def request_client_list(reader, writer):

    # request client list
    message = {"request": "client_list"}
    writer.writer(json.dumps(message).encode())

    # Waiting for response from server
    data_encoded = await reader.read(1024)
    decoded_data = json.loads(data_encoded.decode())

    try:
        # Server response is OK
        if decoded_data["response"] == "OK":
            # "infos" : {"client_list": [[address, ip], [address, ip], ...]}
            return decoded_data["infos"]["client_list"]
        else:
            print("Server KO: <{}>".format(decoded_data["infos"]))
    except KeyError:
        print("Invalid response: <{}>".format(data_encoded.decode()))
        return False


# Handle received messages from peers
async def local_server(reader, writer):
    data_encoded = await reader.read(1024)
    decoded_data = json.loads(data_encoded.decode())
    addr = writer.get_extra_info('peername')

    try:
        # handle server ping
        if decoded_data["request"] == "ping":
            print("Server ping")
            # Write pong
            response = {"response": "pong"}
            writer.write(json.dumps(response).encode())
            await writer.drain()
        # Received a message
        elif decoded_data["request"] == "message":
            # "infos" : {"message": "..."}
            print("Received message from <{}>: <{}>".format(
                addr, decoded_data["infos"]["message"]))

            # Write a response
            response = {"response": "OK"}
            writer.write(json.dumps(response).encode())
            await writer.drain()
        else:
            print("Invalid request from client <{}>: <{}>".format(
                addr, decoded_data["request"]))
    except KeyError:
        print("Invalid message from client <{}>: <{}>".format(
            addr, data_encoded.decode()))


async def start_local_server(self_ip, self_port):
    server = await asyncio.start_server(local_server, self_ip, self_port)

    addresses = ', '.join(str(sock.getsockname()) for sock in server.sockets)
    print(f'Serving locally on {addresses}')

    async with server:
        await server.serve_forever()


async def send_message_to_client(client_addr, client_port):
    reader, writer = await asyncio.open_connection(client_addr, client_port)
    message = {"request": "message", "infos": {"message": "Hello You!"}}
    writer.writer(json.dumps(message).encode())

    data_encoded = await reader.read(1024)
    decoded_data = json.loads(data_encoded.decode())
    addr = writer.get_extra_info('peername')
    try:
        # Server response is OK
        if decoded_data["response"] == "OK":
            print("Message successfully sent to <{}>".format(addr))
        else:
            print("Response to message is KO: <{}>".format(
                decoded_data["infos"]))
    except KeyError:
        print("Invalid response: <{}>".format(data_encoded.decode()))

    writer.close()
    reader.close()


async def message_clients(client_list):
    msg_coros = [send_message_to_client(addr, p) for addr, p in client_list]
    await asyncio.gather(*msg_coros)


async def fetch_client_and_send_messages(server_ip, server_port, time_between_messages):

    while True:
        # Open connection with server
        reader, writer = await asyncio.open_connection(server_ip, server_port)
        # Fetch client list
        client_list = request_client_list(reader, writer)
        # terminate communication with server
        writer.close()
        reader.close()

        # start messaging other clients
        await message_clients(client_list)

        # Wait before sending next messages
        await asyncio.sleep(1)


async def main(server_ip, server_port, self_ip, self_port, max_retry_count, time_between_retry, time_between_messages):
    print("Starting P2P client at <{}:{}>".format(self_ip, self_port))

    # Start a local server to receive messages from other clients
    await start_local_server(self_ip, self_port)

    # Open connection with server
    reader, writer = await asyncio.open_connection(server_ip, server_port)

    # Handshake
    ret = await do_handshake(reader, writer, max_retry_count, time_between_retry)

    # terminate communication with server
    writer.close()
    reader.close()

    if ret:
        # Launch messaging routine
        await fetch_client_and_send_messages(server_ip, server_port, time_between_messages)


if __name__ == "__main__":
    server_ip = '127.0.0.1'
    server_port = 8888

    self_ip = '127.0.0.1'
    self_port = 54001

    max_retry_count = 5

    time_between_retry = 3  # second
    time_between_messages = 10  # second

    self_port = int(
        input("Listening on port (default is {}):".format(self_port)))

    # Start server
    asyncio.run(main(server_ip, server_port, self_ip,
                self_port, max_retry_count, time_between_retry, time_between_messages))
