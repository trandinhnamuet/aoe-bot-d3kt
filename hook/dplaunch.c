// dplaunch.exe - start AoE through DirectPlay Lobby so it opens straight in the multiplayer room
// (the way XArena / GameRanger launch it), as the host of a TCP/IP session.
//
//   dplaunch.exe host "<player name>" "<session name>"
//
// The application is looked up by the session's guidApplication (Rise of Rome) in
// HKLM\SOFTWARE\(WOW6432Node\)Microsoft\DirectPlay\Applications. Exit code 0 = launched.
#define INITGUID
#include <windows.h>
#include <objbase.h>
#include <dplay.h>
#include <dplobby.h>
#include <stdio.h>
#include <string.h>

// {8701C5C1-337B-11d2-839B-00609707F508} Age of Empires: The Rise of Rome
DEFINE_GUID(GUID_AOE_ROR, 0x8701c5c1, 0x337b, 0x11d2, 0x83, 0x9b, 0x00, 0x60, 0x97, 0x07, 0xf5, 0x08);

int main(int argc, char **argv) {
    if (argc < 4 || strcmp(argv[1], "host") != 0) {
        fprintf(stderr, "usage: dplaunch host <player name> <session name>\n");
        return 2;
    }
    CoInitialize(NULL);
    LPDIRECTPLAYLOBBYA lobby1 = NULL;
    HRESULT hr = DirectPlayLobbyCreateA(NULL, &lobby1, NULL, NULL, 0);
    if (FAILED(hr) || !lobby1) { fprintf(stderr, "DirectPlayLobbyCreate failed %08lx\n", hr); return 3; }
    LPDIRECTPLAYLOBBY3A lobby = NULL;
    hr = IDirectPlayLobby_QueryInterface(lobby1, &IID_IDirectPlayLobby3A, (void **)&lobby);
    if (FAILED(hr)) { fprintf(stderr, "QueryInterface(Lobby3A) failed %08lx\n", hr); return 4; }

    // TCP/IP service provider, empty host address (we are the host)
    char addr[256];
    DWORD addr_size = sizeof addr;
    char empty[1] = "";
    hr = IDirectPlayLobby_CreateAddress(lobby, &DPSPGUID_TCPIP, &DPAID_INet, empty, 1, addr, &addr_size);
    if (FAILED(hr)) { fprintf(stderr, "CreateAddress failed %08lx\n", hr); return 5; }

    DPSESSIONDESC2 sd;
    memset(&sd, 0, sizeof sd);
    sd.dwSize = sizeof sd;
    sd.dwFlags = DPSESSION_KEEPALIVE;
    sd.guidApplication = GUID_AOE_ROR;
    sd.dwMaxPlayers = 8;
    sd.lpszSessionNameA = argv[3];
    CoCreateGuid(&sd.guidInstance);

    DPNAME pn;
    memset(&pn, 0, sizeof pn);
    pn.dwSize = sizeof pn;
    pn.lpszShortNameA = argv[2];
    pn.lpszLongNameA = argv[2];

    DPLCONNECTION conn;
    memset(&conn, 0, sizeof conn);
    conn.dwSize = sizeof conn;
    conn.dwFlags = DPLCONNECTION_CREATESESSION;
    conn.lpSessionDesc = &sd;
    conn.lpPlayerName = &pn;
    conn.guidSP = DPSPGUID_TCPIP;
    conn.lpAddress = addr;
    conn.dwAddressSize = addr_size;

    DWORD app_id = 0;
    hr = IDirectPlayLobby_RunApplication(lobby, 0, &app_id, &conn, NULL);
    if (FAILED(hr)) { fprintf(stderr, "RunApplication failed %08lx\n", hr); return 6; }
    printf("launched app_id=%lu\n", app_id);
    fflush(stdout);
    // keep the lobby alive briefly so the game can read its connection settings
    Sleep(15000);
    IDirectPlayLobby_Release(lobby);
    IDirectPlayLobby_Release(lobby1);
    return 0;
}
