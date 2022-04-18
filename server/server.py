import asyncio
import json

# Message format
# {"request" : "<func>", [optional "infos" : { ... }]}
# Response format
# {"response" : "<code>", [optional "infos" : { ... }]}

# Dicts are thread safe thanks to GIL
client_list = {}


async def do_handshake(reader, writer, decoded_data):
    global client_list

    client_addr = decoded_data["infos"]["ip"]
    client_port = decoded_data["infos"]["port"]
    print("Handshake from <{}:{}>".format(client_addr, client_port))

    # insert client into global list
    key = "{}:{}".format(client_addr, client_port)
    if key not in client_list:
        client_list[key] = {"ip": client_addr, "port": client_port}

    # send ok response
    response = {"response": "OK"}
    writer.write(json.dumps(response).encode())
    await writer.drain()


async def do_client_list(reader, writer, decoded_data):
    global client_list

    response = {"response": "OK", "infos": {
        "client_list": [[value["ip"], value["port"]] for value in client_list.values()]
    }}

    # send ok response
    writer.write(json.dumps(response).encode())
    await writer.drain()


async def handle_client(reader, writer):
    data_encoded = await reader.read(1024)
    decoded_data = json.loads(data_encoded.decode())

    try:
        # Client request is "handshake"
        if decoded_data["request"] == "handshake":
            await do_handshake(reader, writer, decoded_data)
        elif decoded_data["request"] == "client_list":
            await do_client_list(reader, writer, decoded_data)
        else:
            print("Invalid client: <{}>".format(decoded_data["infos"]))
    except KeyError:
        print("Invalid request: <{}>".format(data_encoded.decode()))
        return False

    writer.close()


async def start_server(server_ip, server_port):
    server = await asyncio.start_server(
        handle_client, server_ip, server_port)

    addrs = ', '.join(str(sock.getsockname()) for sock in server.sockets)
    print(f'Serving on {addrs}')

    async with server:
        await server.serve_forever()


async def do_one_ping(key, addr, port):
    try:
        reader, writer = await asyncio.open_connection(addr, port)

        # ping the client
        print("Pinging <{}>...".format(key))
        message = {"request": "ping"}
        writer.write(json.dumps(message).encode())
        await writer.drain()

        # is there a pong?
        data_encoded = await reader.read(1024)
        decoded_data = json.loads(data_encoded.decode())
        if not decoded_data["response"] == "pong":
            del client_list[key]
        else:
            print("OK!")
    except:
        del client_list[key]


async def do_pings(time_between_pings):
    global client_list

    while True:
        await asyncio.sleep(time_between_pings)

        ping_coros = [do_one_ping(key, value["ip"], value["port"])
                      for key, value in client_list.items()]

        print("Performing <{}> pings...".format(len(ping_coros)))
        await asyncio.gather(*ping_coros)


async def main(server_ip, server_port, time_between_pings):
    # Start server
    print("Starting server...")
    task_server = asyncio.create_task(start_server(server_ip, server_port))

    # Start ping routine
    print("Starting ping routines...")
    task_pings = asyncio.create_task(do_pings(time_between_pings))
    await task_server
    await task_pings

if __name__ == "__main__":
    server_ip = '127.0.0.1'
    server_port = 8888

    time_between_pings = 15  # seconds

    asyncio.run(main(server_ip, server_port, time_between_pings))
