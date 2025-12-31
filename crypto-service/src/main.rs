//! Project Chimera - Cryptographic Service
//! Ed25519 signing, ChaCha20-Poly1305 encryption, Argon2 password hashing
//! 
//! Enterprise-grade cryptographic operations for the Chimera distributed system

use axum::{
    extract::{Json, State},
    http::StatusCode,
    response::IntoResponse,
    routing::{get, post},
    Router,
};
use base64::{Engine as _, engine::general_purpose::STANDARD as BASE64};
use chacha20poly1305::{
    aead::{Aead, KeyInit},
    ChaCha20Poly1305, Nonce,
};
use ed25519_dalek::{Signature, Signer, SigningKey, Verifier, VerifyingKey};
use rand::rngs::OsRng;
use serde::{Deserialize, Serialize};
use std::{collections::HashMap, sync::Arc};
use tokio::sync::RwLock;
use tracing::{info, warn};

// ═══════════════════════════════════════════════════════════════
// TYPES
// ═══════════════════════════════════════════════════════════════

#[derive(Clone)]
struct AppState {
    keys: Arc<RwLock<KeyStore>>,
    sessions: Arc<RwLock<SessionStore>>,
}

struct KeyStore {
    signing_keys: HashMap<String, SigningKey>,
    encryption_keys: HashMap<String, [u8; 32]>,
}

struct SessionStore {
    sessions: HashMap<String, Session>,
}

#[derive(Clone, Serialize)]
struct Session {
    user_id: String,
    token: String,
    created_at: i64,
    expires_at: i64,
}

// ═══════════════════════════════════════════════════════════════
// REQUEST/RESPONSE TYPES
// ═══════════════════════════════════════════════════════════════

#[derive(Deserialize)]
struct SignRequest {
    user_id: String,
    message: String,
}

#[derive(Serialize)]
struct SignResponse {
    signature: String,
    public_key: String,
}

#[derive(Deserialize)]
struct VerifyRequest {
    user_id: String,
    message: String,
    signature: String,
}

#[derive(Serialize)]
struct VerifyResponse {
    valid: bool,
}

#[derive(Deserialize)]
struct EncryptRequest {
    user_id: String,
    plaintext: String,
}

#[derive(Serialize)]
struct EncryptResponse {
    ciphertext: String,
    nonce: String,
}

#[derive(Deserialize)]
struct DecryptRequest {
    user_id: String,
    ciphertext: String,
    nonce: String,
}

#[derive(Serialize)]
struct DecryptResponse {
    plaintext: String,
}

#[derive(Deserialize)]
struct HashPasswordRequest {
    password: String,
}

#[derive(Serialize)]
struct HashPasswordResponse {
    hash: String,
}

#[derive(Deserialize)]
struct VerifyPasswordRequest {
    password: String,
    hash: String,
}

#[derive(Serialize)]
struct VerifyPasswordResponse {
    valid: bool,
}

#[derive(Deserialize)]
struct CreateSessionRequest {
    user_id: String,
    ttl_seconds: Option<i64>,
}

#[derive(Serialize)]
struct ErrorResponse {
    error: String,
}

// ═══════════════════════════════════════════════════════════════
// HANDLERS
// ═══════════════════════════════════════════════════════════════

async fn health() -> impl IntoResponse {
    Json(serde_json::json!({
        "status": "healthy",
        "service": "chimera-crypto",
        "version": "1.0.0"
    }))
}

/// Generate keypair for user if not exists, then sign message
async fn sign(
    State(state): State<AppState>,
    Json(req): Json<SignRequest>,
) -> Result<Json<SignResponse>, (StatusCode, Json<ErrorResponse>)> {
    let mut keys = state.keys.write().await;
    
    // Get or create signing key for user
    let signing_key = keys.signing_keys
        .entry(req.user_id.clone())
        .or_insert_with(|| SigningKey::generate(&mut OsRng));
    
    // Sign the message
    let signature = signing_key.sign(req.message.as_bytes());
    let verifying_key = signing_key.verifying_key();
    
    Ok(Json(SignResponse {
        signature: BASE64.encode(signature.to_bytes()),
        public_key: BASE64.encode(verifying_key.to_bytes()),
    }))
}

/// Verify a signature
async fn verify(
    State(state): State<AppState>,
    Json(req): Json<VerifyRequest>,
) -> Result<Json<VerifyResponse>, (StatusCode, Json<ErrorResponse>)> {
    let keys = state.keys.read().await;
    
    let signing_key = keys.signing_keys.get(&req.user_id)
        .ok_or_else(|| (
            StatusCode::NOT_FOUND,
            Json(ErrorResponse { error: "User key not found".to_string() })
        ))?;
    
    let verifying_key = signing_key.verifying_key();
    
    let signature_bytes = BASE64.decode(&req.signature)
        .map_err(|_| (
            StatusCode::BAD_REQUEST,
            Json(ErrorResponse { error: "Invalid signature encoding".to_string() })
        ))?;
    
    let signature = Signature::from_slice(&signature_bytes)
        .map_err(|_| (
            StatusCode::BAD_REQUEST,
            Json(ErrorResponse { error: "Invalid signature format".to_string() })
        ))?;
    
    let valid = verifying_key.verify(req.message.as_bytes(), &signature).is_ok();
    
    Ok(Json(VerifyResponse { valid }))
}

/// Encrypt data with ChaCha20-Poly1305
async fn encrypt(
    State(state): State<AppState>,
    Json(req): Json<EncryptRequest>,
) -> Result<Json<EncryptResponse>, (StatusCode, Json<ErrorResponse>)> {
    let mut keys = state.keys.write().await;
    
    // Get or create encryption key for user
    let key = keys.encryption_keys
        .entry(req.user_id.clone())
        .or_insert_with(|| {
            let mut key = [0u8; 32];
            rand::RngCore::fill_bytes(&mut OsRng, &mut key);
            key
        });
    
    let cipher = ChaCha20Poly1305::new_from_slice(key)
        .map_err(|_| (
            StatusCode::INTERNAL_SERVER_ERROR,
            Json(ErrorResponse { error: "Failed to create cipher".to_string() })
        ))?;
    
    // Generate random nonce
    let mut nonce_bytes = [0u8; 12];
    rand::RngCore::fill_bytes(&mut OsRng, &mut nonce_bytes);
    let nonce = Nonce::from_slice(&nonce_bytes);
    
    let ciphertext = cipher.encrypt(nonce, req.plaintext.as_bytes())
        .map_err(|_| (
            StatusCode::INTERNAL_SERVER_ERROR,
            Json(ErrorResponse { error: "Encryption failed".to_string() })
        ))?;
    
    Ok(Json(EncryptResponse {
        ciphertext: BASE64.encode(&ciphertext),
        nonce: BASE64.encode(nonce_bytes),
    }))
}

/// Decrypt data with ChaCha20-Poly1305
async fn decrypt(
    State(state): State<AppState>,
    Json(req): Json<DecryptRequest>,
) -> Result<Json<DecryptResponse>, (StatusCode, Json<ErrorResponse>)> {
    let keys = state.keys.read().await;
    
    let key = keys.encryption_keys.get(&req.user_id)
        .ok_or_else(|| (
            StatusCode::NOT_FOUND,
            Json(ErrorResponse { error: "User key not found".to_string() })
        ))?;
    
    let cipher = ChaCha20Poly1305::new_from_slice(key)
        .map_err(|_| (
            StatusCode::INTERNAL_SERVER_ERROR,
            Json(ErrorResponse { error: "Failed to create cipher".to_string() })
        ))?;
    
    let ciphertext = BASE64.decode(&req.ciphertext)
        .map_err(|_| (
            StatusCode::BAD_REQUEST,
            Json(ErrorResponse { error: "Invalid ciphertext encoding".to_string() })
        ))?;
    
    let nonce_bytes = BASE64.decode(&req.nonce)
        .map_err(|_| (
            StatusCode::BAD_REQUEST,
            Json(ErrorResponse { error: "Invalid nonce encoding".to_string() })
        ))?;
    
    let nonce = Nonce::from_slice(&nonce_bytes);
    
    let plaintext = cipher.decrypt(nonce, ciphertext.as_ref())
        .map_err(|_| (
            StatusCode::BAD_REQUEST,
            Json(ErrorResponse { error: "Decryption failed".to_string() })
        ))?;
    
    Ok(Json(DecryptResponse {
        plaintext: String::from_utf8_lossy(&plaintext).to_string(),
    }))
}

/// Hash password with Argon2
async fn hash_password(
    Json(req): Json<HashPasswordRequest>,
) -> Result<Json<HashPasswordResponse>, (StatusCode, Json<ErrorResponse>)> {
    use argon2::{Argon2, PasswordHasher};
    use argon2::password_hash::SaltString;
    
    let salt = SaltString::generate(&mut OsRng);
    let argon2 = Argon2::default();
    
    let hash = argon2.hash_password(req.password.as_bytes(), &salt)
        .map_err(|_| (
            StatusCode::INTERNAL_SERVER_ERROR,
            Json(ErrorResponse { error: "Password hashing failed".to_string() })
        ))?
        .to_string();
    
    Ok(Json(HashPasswordResponse { hash }))
}

/// Verify password against hash
async fn verify_password(
    Json(req): Json<VerifyPasswordRequest>,
) -> Result<Json<VerifyPasswordResponse>, (StatusCode, Json<ErrorResponse>)> {
    use argon2::{Argon2, PasswordVerifier};
    use argon2::password_hash::PasswordHash;
    
    let parsed_hash = PasswordHash::new(&req.hash)
        .map_err(|_| (
            StatusCode::BAD_REQUEST,
            Json(ErrorResponse { error: "Invalid hash format".to_string() })
        ))?;
    
    let valid = Argon2::default()
        .verify_password(req.password.as_bytes(), &parsed_hash)
        .is_ok();
    
    Ok(Json(VerifyPasswordResponse { valid }))
}

/// Create session token
async fn create_session(
    State(state): State<AppState>,
    Json(req): Json<CreateSessionRequest>,
) -> Result<Json<Session>, (StatusCode, Json<ErrorResponse>)> {
    let mut sessions = state.sessions.write().await;
    
    let now = chrono::Utc::now().timestamp();
    let ttl = req.ttl_seconds.unwrap_or(3600); // 1 hour default
    
    let token = uuid::Uuid::new_v4().to_string();
    
    let session = Session {
        user_id: req.user_id,
        token: token.clone(),
        created_at: now,
        expires_at: now + ttl,
    };
    
    sessions.sessions.insert(token.clone(), session.clone());
    
    Ok(Json(session))
}

// ═══════════════════════════════════════════════════════════════
// MAIN
// ═══════════════════════════════════════════════════════════════

#[tokio::main]
async fn main() {
    // Initialize tracing
    tracing_subscriber::fmt()
        .with_env_filter("info")
        .init();

    info!("═══════════════════════════════════════════════════");
    info!("  🔐 PROJECT CHIMERA - Crypto Service v1.0");
    info!("═══════════════════════════════════════════════════");

    let state = AppState {
        keys: Arc::new(RwLock::new(KeyStore {
            signing_keys: HashMap::new(),
            encryption_keys: HashMap::new(),
        })),
        sessions: Arc::new(RwLock::new(SessionStore {
            sessions: HashMap::new(),
        })),
    };

    let app = Router::new()
        // Health
        .route("/health", get(health))
        // Signing
        .route("/sign", post(sign))
        .route("/verify", post(verify))
        // Encryption
        .route("/encrypt", post(encrypt))
        .route("/decrypt", post(decrypt))
        // Password
        .route("/hash", post(hash_password))
        .route("/verify-password", post(verify_password))
        // Sessions
        .route("/session", post(create_session))
        .with_state(state);

    let port = std::env::var("PORT").unwrap_or_else(|_| "8081".to_string());
    let addr = format!("0.0.0.0:{}", port);
    
    info!("🚀 Crypto service starting on {}", addr);
    info!("   Sign:     POST /sign");
    info!("   Verify:   POST /verify");
    info!("   Encrypt:  POST /encrypt");
    info!("   Decrypt:  POST /decrypt");
    info!("   Hash:     POST /hash");
    info!("   Health:   GET /health");

    let listener = tokio::net::TcpListener::bind(&addr).await.unwrap();
    axum::serve(listener, app).await.unwrap();
}
