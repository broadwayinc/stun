#include <string>
#include <vector>
#include "./include/json.hpp"
#include <signal.h>
#include <iostream>
#include <stdexcept>
#include <curl/curl.h>

#if defined(__linux__ )
   #include <arpa/inet.h>
   #include <sys/socket.h>
   #include <unistd.h>
   #include <netdb.h>
#else
  #include <io.h> 
  #include <winsock2.h> 
  #include <Windows.h>  
  #include <Ws2tcpip.h>
  #pragma comment (lib, "Ws2_32.lib")
  #pragma comment (lib, "Mswsock.lib")
  #pragma warning(disable : 4996)
  typedef unsigned __int64    ssize_t;
#endif

// sudo apt-get install libwebsockets-dev
#include <libwebsockets.h>

// tobuild: g++ stun.cpp -o stun -l curl -l websockets

#include <stdexcept>

std::string resolve_hostname(const std::string& hostname) {
    struct addrinfo hints, *res;
    std::memset(&hints, 0, sizeof(hints));
    hints.ai_family = AF_INET; // Use AF_INET for IPv4
    hints.ai_socktype = SOCK_DGRAM;

    int err = getaddrinfo(hostname.c_str(), nullptr, &hints, &res);
    if (err != 0) {
        std::cerr << "getaddrinfo: " << gai_strerror(err) << std::endl;
        return "";
    }

    char ip_str[INET_ADDRSTRLEN];
    void* addr = &((struct sockaddr_in*)res->ai_addr)->sin_addr;
    inet_ntop(res->ai_family, addr, ip_str, sizeof(ip_str));
    freeaddrinfo(res);

    return std::string(ip_str);
}


#if defined(__linux__)
 std::string stun_client(const std::string& stun_endpoint, int client_port, int &sock) 
#else
 std::string stun_client(const std::string& stun_endpoint, int client_port, SOCKET &sock)  
#endif
{

    std::cout << "STUN client started with endpoint: " << stun_endpoint << " and client port: " << client_port << std::endl;

    std::vector<std::string> endpoint_split;
    size_t pos = 0, found;
    while((found = stun_endpoint.find_first_of(':', pos)) != std::string::npos) {
        endpoint_split.push_back(stun_endpoint.substr(pos, found - pos));
        pos = found + 1;
    }
    endpoint_split.push_back(stun_endpoint.substr(pos));

    if (endpoint_split.size() != 2) {
        throw std::invalid_argument("Invalid STUN endpoint format");
    }

    std::string server_hostname = endpoint_split[0];
    int server_port;
    try {
        server_port = std::stoi(endpoint_split[1]);
    } catch (const std::invalid_argument) {
        std::cerr << "Invalid server port: " << endpoint_split[1] << std::endl;
        throw;
    }

    std::cout << "Resolving hostname: " << server_hostname << std::endl;
    std::string server_ip = resolve_hostname(server_hostname);
    if (server_ip.empty()) {
        std::cerr << "Failed to resolve hostname: " << server_hostname << std::endl;
        return "";
    }

    std::cout << "Resolved server IP: " << server_ip << " and server port: " << server_port << std::endl;

    unsigned char stun_header[20] = {0x00, 0x01, 0x00, 0x00, 0x21, 0x12, 0xA4, 0x42, 0x6F, 0xA2, 0x2B, 0x0D};
                  //0x63, 0xc7, 0x11, 0x7e, 0x07, 0x14, 0x27, 0x8f, 
                  //0x5d, 0xed, 0x32, 0x21);
                  
    std::memset(stun_header + 12, 0, 8);

    
    sock = socket(AF_INET, SOCK_DGRAM, 0);
    if (sock < 0) {
        perror("socket");
        return "";
    }

    sockaddr_in client_addr;
    client_addr.sin_family = AF_INET;
    client_addr.sin_addr.s_addr = INADDR_ANY;
    client_addr.sin_port = htons(client_port);

    if (bind(sock, (struct sockaddr*)&client_addr, sizeof(client_addr)) < 0) {
        perror("bind");
        close(sock);
        sock = 0;
        return "";
    }

    sockaddr_in server_addr;
    server_addr.sin_family = AF_INET;
    server_addr.sin_port = htons(server_port);
    int inet_pton_result = inet_pton(AF_INET, server_ip.c_str(), &server_addr.sin_addr);
    if (inet_pton_result <= 0) {
        if (inet_pton_result == 0) {
            std::cerr << "inet_pton: Invalid address format" << std::endl;
        } else {
            perror("inet_pton");
        }
        close(sock);
        sock = 0;
        return "";
    }

    std::string user_ip = "";

    try {
        std::cout << "Sending STUN request to " << server_ip << ":" << server_port << std::endl;
        ssize_t sent_bytes = sendto(sock, (char *)stun_header, sizeof(stun_header), 0, (struct sockaddr*)&server_addr, sizeof(server_addr));
        if (sent_bytes < 0) {
            perror("sendto");
            close(sock);
            sock = 0;
            return "";
        }
        std::cout << "Sent " << sent_bytes << " bytes" << std::endl;

        unsigned char data[1024];
        socklen_t addr_len = sizeof(server_addr);
        ssize_t len = recvfrom(sock, (char *)data, sizeof(data), 0, (struct sockaddr*)&server_addr, &addr_len);
        if (len < 0) {
            perror("recvfrom");
            close(sock);
            sock = 0;
            return "";
        }

        std::cout << "Received STUN response" << std::endl;

        uint16_t message_type, message_length;
        uint32_t magic_cookie;
        std::memcpy(&message_type, data, 2);
        std::memcpy(&message_length, data + 2, 2);
        std::memcpy(&magic_cookie, data + 4, 4);

        message_type = ntohs(message_type);
        message_length = ntohs(message_length);
        magic_cookie = ntohl(magic_cookie);

        size_t pointer = 20;

        while (pointer < message_length + 20) {
            uint16_t attr_type, attr_length;
            std::memcpy(&attr_type, data + pointer, 2);
            std::memcpy(&attr_length, data + pointer + 2, 2);

            attr_type = ntohs(attr_type);
            attr_length = ntohs(attr_length);

            if (attr_type == 0x0001 || attr_type == 0x0020) { // MAPPED-ADDRESS or XOR-MAPPED-ADDRESS
                if (attr_length == 8) { // IPv4
                    if (len >= pointer + 4 + attr_length) {
                        uint8_t family;
                        uint16_t port;
                        uint8_t ip1, ip2, ip3, ip4;
                        std::memcpy(&family, data + pointer + 5, 1);
                        std::memcpy(&port, data + pointer + 6, 2);
                        std::memcpy(&ip1, data + pointer + 8, 1);
                        std::memcpy(&ip2, data + pointer + 9, 1);
                        std::memcpy(&ip3, data + pointer + 10, 1);
                        std::memcpy(&ip4, data + pointer + 11, 1);

                        // port = ntohs(port);
                        
                        port = ntohs(port);
                        port ^= 0x2112;
                        // ip1 ^= 0x21;
                        // ip2 ^= 0x12;
                        // ip3 ^= 0xA4;
                        // ip4 ^= 0x42;
                        
                        // declare and initialize magic word from stun_header
                        uint8_t magic_word[4];
                        std::memcpy(magic_word, stun_header + 4, 4);
                        ip1 ^= magic_word[0];
                        ip2 ^= magic_word[1];
                        ip3 ^= magic_word[2];
                        ip4 ^= magic_word[3];

                        user_ip = std::to_string(ip1) + "." + std::to_string(ip2) + "." + std::to_string(ip3) + "." + std::to_string(ip4) + ":" + std::to_string(port);
                        break;
                    } else {
                        std::cerr << "Unexpected attr_value length for IPv4: " << attr_length << std::endl;
                    }
                } else if (attr_length == 20) { // IPv6
                    if (len >= pointer + 4 + attr_length) {
                        uint8_t family;
                        uint16_t port;
                        uint16_t ip_parts[8];
                        std::memcpy(&family, data + pointer + 5, 1);
                        std::memcpy(&port, data + pointer + 6, 2);
                        std::memcpy(ip_parts, data + pointer + 8, 16);

                        port = ntohs(port);

                        // declare and initialize magic word from stun_header
                        uint8_t magic_word[16];

                        // fixed magic word
                        // uint8_t magic_word[16] = {0x21, 0x12, 0xA4, 0x42, 0x21, 0x12, 0xA4, 0x42, 0x21, 0x12, 0xA4, 0x42, 0x21, 0x12, 0xA4, 0x42};

                        std::memcpy(magic_word, stun_header + 4, 16); // copy magic word from stun_header

                        // xor with magic word
                        port ^= ntohs(0x2112);
                        for (int i = 0; i < 8; ++i) {
                            uint16_t part = ntohs(ip_parts[i]);
                            part ^= (magic_word[2 * i] << 8) | magic_word[2 * i + 1];
                            ip_parts[i] = htons(part);
                        }

                        std::string ip_address;
                        for (int i = 0; i < 8; ++i) {
                            if (i != 0) ip_address += ":";
                            ip_address += std::to_string(ntohs(ip_parts[i]));
                        }
                        user_ip = ip_address + ":" + std::to_string(port);
                        break;
                    } else {
                        std::cerr << "Unexpected attr_value length for IPv6: " << attr_length << std::endl;
                    }
                }
                break;
            }
            pointer += 4 + attr_length;
        }
    } catch (...) {
        //close(sock);
        throw;
    }

    //close(sock);
    return user_ip;
}
// Structure to hold the room_id, user_id, and user_ip
struct ws_client_data {
    std::string room_id;
    std::string user_id;
    std::string user_ip;
};

// Callback function for WebSocket events
static int callback_ws(struct lws *wsi, enum lws_callback_reasons reason,
                       void *user, void *in, size_t len) {

    ws_client_data *data = (ws_client_data *)user; // user data is in user pointer

    switch (reason) {
        case LWS_CALLBACK_CLIENT_ESTABLISHED: {
            std::cout << "Client connected" << std::endl;
     
            // Request a writeable callback
            lws_callback_on_writable(wsi);
            break;
        }
        case LWS_CALLBACK_CLIENT_RECEIVE: {
            std::cout << "Received data: " << std::string((char *)in, len) << std::endl;

            // Parse the received JSON message
            nlohmann::json received_message = nlohmann::json::parse(std::string((char *)in, len));
            
            // check if there is a key "#notice" in the JSON message
            if (received_message.find("#notice") != received_message.end()) {
                // {"#notice": "User \"helloid\" has joined the message group;0.0.0.0:1234", "#user_id": "helloid"}

                // check if #user_id is same as connected user data->user_id
                if (received_message["#user_id"] == data->user_id) {
                    // this is a message for the user who has connected, thus ignore
                    std::cout << "User has joined the room" << std::endl;
                }

                else {
                    std::string notice = received_message["#notice"];
                    std::cout << "Notice: " << notice << std::endl;

                    // split the notice string by the ';' character. and extract the ip
                    std::string delimiter = ";";
                    size_t pos = notice.find(delimiter);
                    std::string user_ip = notice.substr(pos + 1);

                    std::cout << "User IP: " << user_ip << std::endl;
                    std::cout << "User ID: " << received_message["#user_id"] << std::endl;
                }
            }

            break;
        }
        case LWS_CALLBACK_CLIENT_WRITEABLE: {
            std::cout << "Client is writeable" << std::endl;
            std::cout << "Callback invoked with user data: " << user << std::endl; // Debugging statement
        
            if (!data) {
                std::cerr << "User data is null" << std::endl;
                return 0;
            }

            // once connected, send the room_id, user_id, and user_ip to join the room and let others know
            // once the user has joined the room, the user will be registered in the database as well.
            // you can get list of joined users registered in the database by calling the get_users function

            try {
                nlohmann::json json_message = {
                    {"action", "joinRoom"},
                    {"rid", data->room_id},
                    {"token", data->user_id},
                    {"candidate", data->user_ip}
                };
                std::string json_str = json_message.dump();
                std::cout << "Constructed JSON string: " << json_str << std::endl; // Debugging statement
                size_t message_len = json_str.length();
                unsigned char *buf = new unsigned char[LWS_PRE + message_len];
                memcpy(&buf[LWS_PRE], json_str.c_str(), message_len);
                lws_write(wsi, &buf[LWS_PRE], message_len, LWS_WRITE_TEXT);
                delete[] buf; // Free the allocated memory
                std::cout << "Sent" << std::endl;

            } catch (const std::exception& e) {
                std::cerr << "Exception constructing JSON message: " << e.what() << std::endl;
            }
            
            break;
        }
        case LWS_CALLBACK_CLIENT_CONNECTION_ERROR: {
            if (in && len > 0) {
                std::cerr << "Connection error: " << std::string((const char *)in, len) << std::endl;
            } else {
                std::cerr << "Connection error: unknown reason" << std::endl;
            }
            break;
        }
        case LWS_CALLBACK_CLOSED: {
            std::cout << "Client connection closed" << std::endl;
            break;
        }
        default:
            break;
    }

    return 0;
}

// Protocols array
static struct lws_protocols protocols[] = {
    {
        "ws-protocol",
        callback_ws,
        sizeof(ws_client_data),
        65536,
    },
    { NULL, NULL, 0, 0 } // terminator
};


// Function to handle the response data
size_t WriteCallback(void* contents, size_t size, size_t nmemb, void* userp) {
    ((std::string*)userp)->append((char*)contents, size * nmemb);
    return size * nmemb;
}

// Function to get users
nlohmann::json get_users(const std::string& room) {
    // Define the base URL
    std::string url = "https://4b6zwxd0l4.execute-api.us-east-1.amazonaws.com/api/get-ws-group";
    
    // Define the query parameters
    std::string params = "room=" + room;

    // Append the query string to the URL
    std::string full_url = url + "?" + params;

    std::cout << "full_url: " << full_url << std::endl;

    // Initialize CURL
    CURL* curl;
    CURLcode res;
    curl_global_init(CURL_GLOBAL_DEFAULT);
    
    std::string readBuffer;

    curl = curl_easy_init();
    
    if(curl) {
        curl_easy_setopt(curl, CURLOPT_URL, full_url.c_str());
        curl_easy_setopt(curl, CURLOPT_WRITEFUNCTION, WriteCallback);
        curl_easy_setopt(curl, CURLOPT_WRITEDATA, &readBuffer);
        res = curl_easy_perform(curl);
        if(res != CURLE_OK) {
            std::cerr << "curl_easy_perform() failed: " << curl_easy_strerror(res) << std::endl;
            return {};
        }
        curl_easy_cleanup(curl);
       
        
    }

    // Parse the JSON response
    auto data = nlohmann::json::parse(readBuffer);

    // Access the "list" key
    auto listData = data["list"];
    
    return listData;
}

std::string extract_user_id(const std::string& cnd_value) {
    // Find the position of the '#' character
    size_t pos = cnd_value.find('#');
    if (pos != std::string::npos) {
        // Extract the substring after the '#' character
        return cnd_value.substr(pos + 1);
    }
    return "";
}

int main() {
    std::string stun_server_url = "stun.broadwayinc.computer:3468";
    //std::string stun_server_url = "stun.l.google.com:19302";
    int client_port = 1234;
    
    #ifndef __linux__      	  
     WORD sockVersion = MAKEWORD(2, 2);
     WSADATA data;
     if (WSAStartup(sockVersion, &data) != 0)
     {
         return 0;
     }
     #endif

    #if defined(__linux__)
        int stun_socket;
    #else
        SOCKET stun_socket;
    #endif
    
    std::string candidate = stun_client(stun_server_url, client_port, stun_socket);

    std::cout << "stun_client>: My IP: " << candidate << std::endl;

    std::string room_id = "Id001"; // choose a room id
    std::string token = "Test-Hello"; // choose a user id
  
  
    auto users = get_users(room_id);
    
    // Get the length of the users list
    size_t length = users.size();
    std::cout << "Number of users: " << length << std::endl;
    
    // Iterate over the users list and access each value
    // [{"cnd":"21.92.172.222:4395","uid":"stunpunch#user_id"}, ...]
    for (const auto& user : users) {
        std::cout << "-" << std::endl;
        std::string user_id = extract_user_id(user["uid"]);
        std::string user_ip = (user["cnd"]);
        std::cout << "User ID: " << user_id << std::endl;
        std::cout << "User IP: " << user_ip << std::endl;
        //std::cout << "User IP: " << user["cnd"] << std::endl;
    }
    
    // websocket
    struct lws_context_creation_info info;
    memset(&info, 0, sizeof(info));
    info.port = CONTEXT_PORT_NO_LISTEN;
    info.protocols = protocols;
    info.gid = -1;
    info.uid = -1;
    info.options = LWS_SERVER_OPTION_DO_SSL_GLOBAL_INIT;

    struct lws_context *context = lws_create_context(&info);
    if (context == NULL) {
        std::cerr << "lws_create_context failed" << std::endl;
        return -1;
    }

    std::string path = "/api?token=" + token;
    struct lws_client_connect_info ccinfo = {0};
    ccinfo.context = context;
    ccinfo.address = "yaqlgf8dek.execute-api.us-east-1.amazonaws.com";
    ccinfo.port = 443;
    ccinfo.path = path.c_str();
    ccinfo.host = "yaqlgf8dek.execute-api.us-east-1.amazonaws.com";
    ccinfo.origin = "origin";
    ccinfo.protocol = protocols[0].name;
    ccinfo.ssl_connection = LCCSCF_USE_SSL;

    // Allocate memory for user data and set the room_id, user_id, and user_ip
    ws_client_data *user_data = new ws_client_data;
    user_data->room_id = room_id;
    user_data->user_id = token; // Example user ID
    user_data->user_ip = candidate; // Example user IP
    ccinfo.userdata = user_data; // Pass the user data to the connection

    // connect to websocket, pass the user data
    struct lws *wsi = lws_client_connect_via_info(&ccinfo);
    if (wsi == NULL) {
        std::cerr << "Failed to initiate connection" << std::endl;
        lws_context_destroy(context);
        delete user_data; // Free the allocated memory
        return -1;
    }

    // Run the event loop, exit when exit_requested is set, keep it running
    while (lws_service(context, 1000) >= 0);

    lws_context_destroy(context);
    delete user_data; // Free the allocated memory
    return 0;
}