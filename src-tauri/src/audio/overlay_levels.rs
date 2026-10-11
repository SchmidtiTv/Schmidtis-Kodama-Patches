use serde::Serialize;
use std::net::{Ipv4Addr, SocketAddrV4, UdpSocket};
use std::sync::atomic::{AtomicU16, Ordering};
use std::sync::Arc;
use std::time::Duration;

const BAND_COUNT: usize = 48;
const DEMAND_URL: &str = "http://localhost:9847/overlay/levels/demand";

struct PublisherState {
    port: AtomicU16,
    socket: Option<UdpSocket>,
}

/// Sends the latest analysis frame only while an OBS overlay requests it.
#[derive(Clone)]
pub struct OverlayLevelsPublisher {
    state: Arc<PublisherState>,
}

impl OverlayLevelsPublisher {
    pub fn new() -> Self {
        let socket = UdpSocket::bind((Ipv4Addr::LOCALHOST, 0))
            .ok()
            .and_then(|socket| {
                socket.set_nonblocking(true).ok()?;
                Some(socket)
            });
        let state = Arc::new(PublisherState {
            port: AtomicU16::new(0),
            socket,
        });
        let weak = Arc::downgrade(&state);
        std::thread::Builder::new()
            .name("kodama-overlay-demand".into())
            .spawn(move || {
                let Ok(client) = reqwest::blocking::Client::builder()
                    .timeout(Duration::from_millis(750))
                    .no_proxy()
                    .build()
                else {
                    return;
                };
                loop {
                    if weak.strong_count() == 0 {
                        return;
                    }
                    let port = client
                        .get(DEMAND_URL)
                        .send()
                        .and_then(reqwest::blocking::Response::error_for_status)
                        .and_then(|response| response.json::<Demand>())
                        .map(|demand| demand.port)
                        .unwrap_or(0);
                    let Some(state) = weak.upgrade() else {
                        return;
                    };
                    state.port.store(port, Ordering::Relaxed);
                    drop(state);
                    std::thread::sleep(Duration::from_secs(1));
                }
            })
            .ok();
        Self { state }
    }

    pub fn port(&self) -> u16 {
        if self.state.socket.is_none() {
            return 0;
        }
        self.state.port.load(Ordering::Relaxed)
    }

    /// Never waits for network capacity; an overloaded consumer may skip frames.
    pub fn publish(&self, bands: &[f32], level: f32) {
        let port = self.port();
        if port == 0 {
            return;
        }
        let Some(socket) = &self.state.socket else {
            return;
        };
        let mut bounded_bands = [0.0; BAND_COUNT];
        for (dest, source) in bounded_bands.iter_mut().zip(bands) {
            *dest = normalized(*source);
        }
        let frame = Frame {
            bands: &bounded_bands,
            level: normalized(level),
        };
        if let Ok(data) = serde_json::to_vec(&frame) {
            let _ = socket.send_to(&data, SocketAddrV4::new(Ipv4Addr::LOCALHOST, port));
        }
    }
}

#[derive(serde::Deserialize)]
struct Demand {
    port: u16,
}

#[derive(Serialize)]
struct Frame<'a> {
    bands: &'a [f32],
    level: f32,
}

fn normalized(value: f32) -> f32 {
    if value.is_finite() {
        value.clamp(0.0, 1.0)
    } else {
        0.0
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn publisher_emits_bounded_frames_for_requested_port() {
        let receiver = UdpSocket::bind((Ipv4Addr::LOCALHOST, 0)).unwrap();
        receiver
            .set_read_timeout(Some(Duration::from_secs(1)))
            .unwrap();
        let publisher = OverlayLevelsPublisher {
            state: Arc::new(PublisherState {
                port: AtomicU16::new(receiver.local_addr().unwrap().port()),
                socket: Some(UdpSocket::bind((Ipv4Addr::LOCALHOST, 0)).unwrap()),
            }),
        };
        publisher.publish(&[f32::NAN, -1.0, 2.0], f32::INFINITY);
        let mut buffer = [0; 8192];
        let length = receiver.recv(&mut buffer).unwrap();
        let frame: serde_json::Value = serde_json::from_slice(&buffer[..length]).unwrap();
        let bands = frame["bands"].as_array().unwrap();
        assert_eq!(bands.len(), BAND_COUNT);
        assert_eq!(bands[0], 0.0);
        assert_eq!(bands[1], 0.0);
        assert_eq!(bands[2], 1.0);
        assert_eq!(frame["level"], 0.0);
    }
}
