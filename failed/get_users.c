// This is an attempt to call get request to get users with C.

#include <stdio.h>
#include <stdlib.h>
#include <string.h>

// sudo apt-get install libcurl4-openssl-dev
// sudo apt-get install libcjson-dev
#include <curl/curl.h>
#include <cjson/cJSON.h>

// cc -o get_users get_users.c -lcurl -lcjson

struct string
{
    char *ptr;
    size_t len;
};

void init_string(struct string *s)
{
    s->len = 0;
    s->ptr = malloc(s->len + 1);
    if (s->ptr == NULL)
    {
        fprintf(stderr, "malloc() failed\n");
        exit(EXIT_FAILURE);
    }
    s->ptr[0] = '\0';
}

size_t writefunc(void *ptr, size_t size, size_t nmemb, struct string *s)
{
    size_t new_len = s->len + size * nmemb;
    s->ptr = realloc(s->ptr, new_len + 1);
    if (s->ptr == NULL)
    {
        fprintf(stderr, "realloc() failed\n");
        exit(EXIT_FAILURE);
    }
    memcpy(s->ptr + s->len, ptr, size * nmemb);
    s->ptr[new_len] = '\0';
    s->len = new_len;

    return size * nmemb;
}

char **get_users(const char *room, int *count)
{
    CURL *curl;
    CURLcode res;
    char full_url[512];
    struct string s;
    init_string(&s);

    curl = curl_easy_init(); // returns nothing... why?
    if (curl)
    {
        printf("curl");
        sprintf(full_url, "https://4b6zwxd0l4.execute-api.us-east-1.amazonaws.com/api/get-ws-group?room=%s", room);
        curl_easy_setopt(curl, CURLOPT_URL, full_url);
        curl_easy_setopt(curl, CURLOPT_WRITEFUNCTION, writefunc);
        curl_easy_setopt(curl, CURLOPT_WRITEDATA, &s);
        res = curl_easy_perform(curl);
        if (res != CURLE_OK)
        {
            fprintf(stderr, "curl_easy_perform() failed: %s\n", curl_easy_strerror(res));
        }
        curl_easy_cleanup(curl);

        cJSON *json = cJSON_Parse(s.ptr);
        if (json == NULL)
        {
            printf("json null");
            return NULL;
        }

        cJSON *list = cJSON_GetObjectItemCaseSensitive(json, "list");
        if (!cJSON_IsArray(list))
        {
            printf("!cJSON_IsArray");
            cJSON_Delete(json);
            return NULL;
        }

        *count = cJSON_GetArraySize(list);
        char **users = malloc(*count * sizeof(char *));
        if (users == NULL)
        {
            fprintf(stderr, "malloc() failed\n");
            exit(EXIT_FAILURE);
        }

        cJSON *item;
        int i = 0;
        cJSON_ArrayForEach(item, list)
        {
            if (cJSON_IsString(item) && (item->valuestring != NULL))
            {
                users[i] = strdup(item->valuestring);
                i++;
            }
        }

        cJSON_Delete(json);
        free(s.ptr);

        return users; // Return the list of strings
    }
    return NULL; // In case of failure
}

int main()
{
    int count = 0;
    char **users = get_users("hello", &count);
    for (int i = 0; i < count; i++)
    {
        printf("%s\n", users[i]);
        free(users[i]); // Free each string
    }
    free(users); // Free the array of strings
    return 0;
}