# LookingGlass: forward secure, distributed, pseudonymous email

---

# Background / Overview

  Email encryption usability is awful.  PGP, king of the roost for almost 25 years now, requires a ridiculous amount of domain-specific knowledge to install and use (ever tried to walk multiple users on differing platforms through communicating?) - let alone authentication (the web-of-trust model requires a significant amount of buy-in from users).  User interface for crypto in general is user-hostile and artless (why do I have to pick my key length for *everything*?).
  
  Anonymity software is hit or miss.  Tor has excellent usability with the browser bundle - and then promptly undercuts it by allowing javascript by default.  Sad emoticon.  I2P doesn't have the social capital (or the free RAM) to match up just yet.  Freenet is stillborn.

  LookingGlass takes these existing technologies and a few others ([none my own](https://www.schneier.com/blog/archives/2011/04/schneiers_law.html)) and puts them together with a UI meant to not suck, to be usable by 80% of the intended audience, out of the box.

  LookingGlass email is burn-on-view.  It is local to the user.  It is pseudonymous.  LookingGlass doesn't care about power users, and sets **all** the defaults so all you need to do is pick some passphrases.

  LookingGlass does *not* interact with clearnet email addresses.  The possibility exists for there to be relay nodes between Tor's _.onion_ domain and clearnet email - but presently that is a wishlist item.

  There are a *lot* of wishlist items, but I have run out of steam to do this gratis.  I am releasing it to see what sort of reception it gets, and I'll go from there.

---

## User interface

  LookingGlass is meant to be run on a local, headless (without monitor), always-on computer.  Installation consists of copying a disk image to an SD card, inserting that into a Raspberry Pi, and plugging it into your local network (preferably behind a router).
  
  The user is presented with a webmail interface that guides them through setup, as well as the steps in securing the conversations with their contacts.  Think of it as a security appliance, like a network printer.

  Communication between LookingGlass servers is over the Tor network, from anonymous node to anonymous node (see below).  This allows email free of centralized servers, as well as identifiers - all of this is transparent to the user.

---

## Technologies used

* ### Hardware / Operating System

  The [Raspberry Pi](http://www.raspberrypi.org/) is a credit-card sized single-board computer costing around $40 USD.
  
  [Debian](https://www.debian.org/) (specifically [raspbian](http://www.raspbian.org/)) was chosen as the operating system.  Debian is a mature distribution, with over twenty years of development behind it.  LookingGlass was written to the operating system and not the hardware, to remain portable.
  
  The release methodology of LookingGlass will favor Raspberry Pi users but be portable across Debian platforms - this would allow a hosted LookingGlass instance to be installed onto a VPS server.

* ### Disk Encryption

  [LUKS](https://en.wikipedia.org/wiki/Linux_Unified_Key_Setup) is the built-in Linux drive encryption.  By default, it uses [AES](http://en.wikipedia.org/wiki/Advanced_Encryption_Standard).

  User data (mail spool, address book, ephemeral encryption keys, Tor hidden service address) are kept encrypted.  Queued messages arrive encrypted under Axolotl (see below), and are spooled to a local encrypted volume - they are only decrypted on demand after the user has entered their passphrase.
  
  Loss of power means all incriminating data should be unrecoverable without the user's passphrase.

* ### Public Key Cryptography

  [GnuPG](https://www.gnupg.org/) implements [RFC4880](https://www.ietf.org/rfc/rfc4880.txt) - PGP public key.  This is used as a fallback protocol to allow clients to communicate while forward-secret communications are negotiated.

* ### Forward-secret Cryptography

  [Axolotl](https://github.com/trevp/axolotl/wiki) is a [forward secret](https://en.wikipedia.org/wiki/Perfect_forward_secrecy) encryption algorithm designed to limit the damage of key compromise.  Axolotl underlies [TextSecure's](https://whispersystems.org/) software.
  
  LookingGlass adapted the Axolotl implementation [PyAxo](https://github.com/rxcomm/pyaxo), "armoring" the interchange format for email by encapsulating it in [Base64](https://en.wikipedia.org/wiki/Base64) and [JSON](https://en.wikipedia.org/wiki/JSON) - well known standards.

  Using Axolotl, email becomes 'read once' - messages are securely deleted upon display.

  [See also.](https://www.whispersystems.org/blog/advanced-ratcheting/)

* ### [Socialist Millionaire Protocol](http://twistedoakstudios.com/blog/Post3724_explain-it-like-im-five-the-socialist-millionaire-problem-and-secure-multi-party-computation)

  Authentication of end user identity is done via the Socialist Millionaire Protocol - a [zero knowledge](https://en.wikipedia.org/wiki/Zero-knowledge_proof) proof.  This is the same protocol [OTR](https://otr.cypherpunks.ca/Protocol-v3-4.0.0.html) uses for authentication, but is done over email rather than chat.
  
  Key fingerprints are folded into the shared secret the two parties will compare against each other, eliminating man-in-the-middle attacks.

* ### [Tor](https://www.torproject.org)

  Tor uses [onion routing](https://en.wikipedia.org/wiki/Onion_routing) to anonymize network traffic.  One of the features it provides is known as [hidden services](https://www.torproject.org/docs/hidden-services.html.en) - a method of obscuring the location of a server.

  Each LookingGlass server expects email from the Tor network, and other LookingGlass clients connect via its hidden service address.  This is again adapted from a chat client in present use - [TorChat](https://en.wikipedia.org/wiki/TorChat).

---

# I WANT TO DO THIS

Getting started guide available [here](https://sdtrssmsbmw7eqm4.tor2web.org) or over Tor [here](http://sdtrssmsbmw7eqm4.onion).
