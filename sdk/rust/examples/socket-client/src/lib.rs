//! TCP and UDP echo clients, and DNS, using Rust's standard library.
//!
//! Build with `wasm32-wasip2`. `tools/octo wasm build` records the required
//! host API `wasm.sockets@1` and discloses `net`; desktop RC5 has no sockets.
//! No SDK networking wrapper or async runtime is needed. TCP/UDP carry
//! plaintext here: use a suitable TLS/protocol implementation for real data.

#[octosense_component::export]
pub mod functions {
    use std::io::{ErrorKind, Read, Write};
    use std::net::{SocketAddr, TcpStream, ToSocketAddrs, UdpSocket};
    use std::time::{Duration, Instant};

    const TIMEOUT: Duration = Duration::from_millis(500);
    const MAX_MESSAGE: usize = 1024;

    fn payload(message: &str) -> Result<&[u8], String> {
        if message.is_empty() || message.len() > MAX_MESSAGE {
            return Err("echo message must contain 1–1024 UTF-8 bytes".into());
        }
        Ok(message.as_bytes())
    }

    /// DNS through WASI; return addresses as strings that cross the SDK ABI.
    pub fn resolve(host: &str, port: u16) -> Result<Vec<String>, String> {
        let addresses = (host, port).to_socket_addrs().map_err(|e| e.to_string())?;
        Ok(addresses.take(16).map(|addr| addr.to_string()).collect())
    }

    /// One bounded request to a TCP echo server at a numeric IP:port.
    pub fn tcp_echo(address: &str, message: &str) -> Result<String, String> {
        let bytes = payload(message)?;
        let address: SocketAddr = address.parse().map_err(|e| format!("address: {e}"))?;
        let mut stream =
            TcpStream::connect_timeout(&address, TIMEOUT).map_err(|e| e.to_string())?;
        stream
            .set_read_timeout(Some(TIMEOUT))
            .map_err(|e| e.to_string())?;
        stream
            .set_write_timeout(Some(TIMEOUT))
            .map_err(|e| e.to_string())?;
        stream.write_all(bytes).map_err(|e| e.to_string())?;
        let mut reply = vec![0; bytes.len()];
        stream.read_exact(&mut reply).map_err(|e| e.to_string())?;
        String::from_utf8(reply).map_err(|e| e.to_string())
        // stream drops here, closing the socket even if a preceding ? returns.
    }

    /// One bounded request to a UDP echo server at a numeric IP:port.
    pub fn udp_echo(address: &str, message: &str) -> Result<String, String> {
        let bytes = payload(message)?;
        let address: SocketAddr = address.parse().map_err(|e| format!("address: {e}"))?;
        let local = if address.is_ipv4() {
            "0.0.0.0:0"
        } else {
            "[::]:0"
        };
        let socket = UdpSocket::bind(local).map_err(|e| format!("UDP bind: {e}"))?;
        // Rust's WASI UDP backend does not implement set_read_timeout or
        // set_write_timeout. Poll nonblocking with a clock deadline instead.
        socket.set_nonblocking(true).map_err(|e| e.to_string())?;
        socket
            .connect(address)
            .map_err(|e| format!("UDP connect: {e}"))?;
        socket.send(bytes).map_err(|e| format!("UDP send: {e}"))?;
        let mut reply = [0; MAX_MESSAGE];
        let deadline = Instant::now() + TIMEOUT;
        let length = loop {
            match socket.recv(&mut reply) {
                Ok(length) => break length,
                Err(error) if error.kind() == ErrorKind::WouldBlock => {
                    if Instant::now() >= deadline {
                        return Err("UDP echo timed out".into());
                    }
                    std::thread::sleep(Duration::from_millis(5));
                }
                Err(error) => return Err(format!("UDP receive: {error}")),
            }
        };
        String::from_utf8(reply[..length].to_vec()).map_err(|e| e.to_string())
    }
}
