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
    await writer.drain()

    # Waiting for OK from server
    data_encoded = await reader.read(1024)
    decoded_data = json.loads(data_encoded.decode())
    print("Data recieved from server: <{}>".format(data_encoded.decode()))

    try:
        # Server response is OK
        if decoded_data["response"] == "OK":
            print("OK from server: <{}>".format(data_encoded.decode()))
            return True
        else:
            print("Server KO: <{}>".format(decoded_data["infos"]))
            return False
    except KeyError:
        print("Invalid response: <{}>".format(data_encoded.decode()))
        return False


# Try to do the handshake multiple time
async def do_handshake(server_ip, server_port, try_count, max_retry_count, time_between_retry):
    # Recursive stop condition
    if try_count == max_retry_count:
        return False
    else:
        try:
            reader, writer = await asyncio.open_connection(server_ip, server_port)
            ret = await handshake(reader, writer)
            if ret:
                # We're good, terminate communication with server and return
                writer.close()
                return ret
            else:
                # Not good, fallback on retry
                print("Could not do handshake with the server...")
        except ConnectionRefusedError:
            # Not good, fallback on retry
            print("Could not contact the server...")

        # Retrying
        await asyncio.sleep(time_between_retry)
        print("Retrying...")
        return do_handshake(server_ip, server_port, try_count + 1, max_retry_count, time_between_retry)


# Request the client list from the server
async def request_client_list(reader, writer):

    # request client list
    message = {"request": "client_list"}
    writer.write(json.dumps(message).encode())
    await writer.drain()

    # Waiting for response from server
    data_encoded = await reader.read(1024)
    decoded_data = json.loads(data_encoded.decode())

    try:
        # Server response is OK
        if decoded_data["response"] == "OK":
            print("OK from server for client list: <{}>".format(
                decoded_data["infos"]["client_list"]))
            # "infos" : {"client_list": [[address, ip], [address, ip], ...]}
            return decoded_data["infos"]["client_list"]
        else:
            print("Server KO: <{}>".format(decoded_data["infos"]))
    except KeyError:
        print("Invalid response: <{}>".format(data_encoded.decode()))
        return []


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
    try:
        reader, writer = await asyncio.open_connection(client_addr, client_port)
        message = {"request": "message", "infos": {"message": "Hello You!"}}
        writer.write(json.dumps(message).encode())
        await writer.drain()

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
    except ConnectionRefusedError:
        print("Warning: could not connect to <{}:{}>!".format(
            client_addr, client_port))


async def message_clients(client_list, self_ip, self_port):
    # filter out ourself from the list
    valid_client_list = [
        item for item in client_list if item[0] != self_ip or item[1] != self_port]

    # Debug
    # print(valid_client_list)

    msg_coros = [send_message_to_client(addr, p)
                 for addr, p in valid_client_list]

    if len(valid_client_list) > 0:
        await asyncio.gather(*msg_coros)


async def fetch_client_and_send_messages(server_ip, server_port, time_between_messages, self_ip, self_port, max_retry_count, time_between_retry):
    is_server_online = True  # we enter this routine online if server is online at launch
    client_list = []

    while True:
        try:
            # Open connection with server
            reader, writer = await asyncio.open_connection(server_ip, server_port)
            # Fetch client list
            client_list = await request_client_list(reader, writer)
            # terminate communication with server
            writer.close()
        except ConnectionRefusedError:
            is_server_online = False
            print("Warning: server is offline!")

        # start messaging other clients
        await message_clients(client_list, self_ip, self_port)
        # Wait before sending next messages
        await asyncio.sleep(time_between_messages)
        # Redo a handshake in case server went offline and has its client_list empty
        if not is_server_online:
            is_server_online = await do_handshake(server_ip, server_port, 0, max_retry_count, time_between_retry)


async def main(server_ip, server_port, self_ip, self_port, max_retry_count, time_between_retry, time_between_messages):
    print("Starting P2P client at <{}:{}>".format(self_ip, self_port))

    # Start a local server to receive messages from other clients
    task_local_server = asyncio.create_task(
        start_local_server(self_ip, self_port))

    # initial handshake
    ret = await do_handshake(server_ip, server_port, 0, max_retry_count, time_between_retry)

    if ret:
        # Launch messaging routine
        await fetch_client_and_send_messages(server_ip, server_port, time_between_messages, self_ip, self_port, max_retry_count, time_between_retry)

    await task_local_server

if __name__ == "__main__":
    server_ip = '127.0.0.1'
    server_port = 8888

    self_ip = '127.0.0.1'
    self_port = 54001

    max_retry_count = 5

    time_between_retry = 3  # second
    time_between_messages = 10  # second

    input_port = input("Listening on port (default is {}):".format(self_port))
    if not len(input_port) == 0:
        self_port = int(input_port)

    # Start server
    asyncio.run(main(server_ip, server_port, self_ip,
                self_port, max_retry_count, time_between_retry, time_between_messages))
